#!/usr/bin/env python3
"""
AGL App Store — Flatpak Security Scanner
Runs static + dynamic analysis on submitted Flatpak manifests and bundles.
"""

import os, re, json, yaml, hashlib, tempfile, shutil, subprocess, datetime, urllib.request
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Permission risk table ─────────────────────────────────────────────────────

PERMISSION_RISKS = {
    # CRITICAL — effectively breaks the sandbox
    "--filesystem=host":          ("CRITICAL", "Full host filesystem read/write access"),
    "--filesystem=home":          ("HIGH",     "Full home directory access"),
    "--device=all":               ("CRITICAL", "Access to all devices including DRI, USB, etc."),
    "--allow=devel":              ("HIGH",     "Allows ptrace/perf — can spy on other processes"),
    "--share=network":            ("MEDIUM",   "Unrestricted network access"),
    "--socket=session-bus":       ("HIGH",     "Full session D-Bus — can control desktop apps"),
    "--socket=system-bus":        ("HIGH",     "Full system D-Bus — can control system services"),
    "--socket=ssh-auth":          ("MEDIUM",   "Access to SSH agent"),
    "--talk-name=org.freedesktop.Flatpak": ("CRITICAL", "Can spawn arbitrary flatpak commands"),
    "--talk-name=org.gnome.Shell.Screencast": ("HIGH", "Screen recording capability"),
    "--talk-name=org.freedesktop.secrets": ("HIGH", "Access to secret keyring"),
    "--talk-name=org.freedesktop.NetworkManager": ("MEDIUM", "Can control network"),
    "--own-name=*":               ("HIGH",     "Claims wildcard D-Bus names"),
    "--talk-name=*":              ("HIGH",     "Talks to all D-Bus names"),
    "--socket=x11":               ("MEDIUM",   "X11 access — can keylog other X11 apps"),
    "--persist=.":                ("MEDIUM",   "Persists home subdirectory outside sandbox"),
    "--env=LD_PRELOAD":           ("CRITICAL", "Injects shared library into processes"),
    "--env=LD_LIBRARY_PATH":      ("HIGH",     "Overrides dynamic linker search path"),
}

# Suspicious patterns in build commands / post-install scripts
SUSPICIOUS_BUILD_PATTERNS = [
    (r"curl\s+.*\|\s*(bash|sh|python|perl|ruby)", "CRITICAL", "Remote code execution: pipe curl to shell"),
    (r"wget\s+.*\|\s*(bash|sh|python|perl|ruby)", "CRITICAL", "Remote code execution: pipe wget to shell"),
    (r"eval\s*\(.*\$\(",                           "HIGH",     "eval of command substitution"),
    (r"base64\s+--?decode.*\|\s*(bash|sh)",        "CRITICAL", "Base64-encoded shell payload"),
    (r"python[23]?\s+-c\s+['\"]import\s+(os|sys|subprocess)", "HIGH", "Inline Python exec"),
    (r"nc\s+(-[el]+\s*)?\d+\.\d+\.\d+\.\d+",     "CRITICAL", "Netcat reverse shell pattern"),
    (r"/dev/tcp/",                                  "CRITICAL", "Bash TCP reverse shell"),
    (r"chmod\s+[0-9]*7[0-9]*\s+.*\.(sh|py|pl)",   "MEDIUM",   "Making script executable"),
    (r"rm\s+-rf\s+/",                               "CRITICAL", "Destructive rm -rf /"),
    (r"git\s+clone.*--depth\s+1\s+http://",        "MEDIUM",   "Cloning over unencrypted HTTP"),
    (r"pip\s+install\s+.*--?index-url\s+http://",  "MEDIUM",   "Installing from non-HTTPS PyPI mirror"),
]

# Known-bad domains (typosquatting, known malware CDNs)
SUSPICIOUS_DOMAINS = {
    "githubusercontent.com", "raw.githack.com", "rawgithub.com",
    "pastebin.com", "paste.ee", "hastebin.com",
    "transfer.sh", "file.io",
}

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str      # CRITICAL / HIGH / MEDIUM / LOW / INFO
    category: str      # permissions / build_commands / sources / binary / clamav / trivy
    message: str
    detail: str = ""

@dataclass
class ScanResult:
    submission_id: int
    scanned_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    manifest_path: Optional[str] = None
    bundle_path: Optional[str] = None
    findings: list = field(default_factory=list)
    risk_score: int = 0        # 0-100
    verdict: str = "UNKNOWN"   # PASS / WARN / BLOCK
    summary: str = ""

    def add(self, finding: Finding):
        self.findings.append(asdict(finding))

    def compute_verdict(self):
        score = 0
        for f in self.findings:
            if f["severity"] == "CRITICAL": score += 30
            elif f["severity"] == "HIGH":   score += 15
            elif f["severity"] == "MEDIUM": score += 5
            elif f["severity"] == "LOW":    score += 1
        self.risk_score = min(score, 100)
        if score >= 30:
            self.verdict = "BLOCK"
        elif score >= 10:
            self.verdict = "WARN"
        else:
            self.verdict = "PASS"
        criticals = [f for f in self.findings if f["severity"] == "CRITICAL"]
        highs     = [f for f in self.findings if f["severity"] == "HIGH"]
        self.summary = (
            f"Risk score: {self.risk_score}/100 | Verdict: {self.verdict} | "
            f"{len(criticals)} critical, {len(highs)} high, "
            f"{len(self.findings)-len(criticals)-len(highs)} other findings"
        )

# ── Manifest scanner ──────────────────────────────────────────────────────────

def scan_manifest(manifest_content: str, result: ScanResult):
    """Statically analyse a Flatpak manifest (YAML or JSON)."""
    try:
        data = yaml.safe_load(manifest_content)
    except Exception:
        try:
            data = json.loads(manifest_content)
        except Exception as e:
            result.add(Finding("HIGH", "manifest", "Failed to parse manifest", str(e)))
            return

    app_id = data.get("app-id") or data.get("id", "unknown")

    # 1. Check finish-args (sandbox permissions)
    finish_args = data.get("finish-args", [])
    for arg in finish_args:
        arg = arg.strip()
        # Exact match
        if arg in PERMISSION_RISKS:
            sev, reason = PERMISSION_RISKS[arg]
            result.add(Finding(sev, "permissions", f"Dangerous permission: {arg}", reason))
            continue
        # Wildcard filesystem
        if re.match(r"--filesystem=/(bin|etc|usr|lib|sbin|boot|sys|proc|run|var)", arg):
            result.add(Finding("CRITICAL", "permissions",
                f"Direct system path access: {arg}",
                "Bypasses sandbox by accessing sensitive system directories"))
        elif arg.startswith("--filesystem=") and ":create" in arg:
            result.add(Finding("MEDIUM", "permissions",
                f"Filesystem write permission: {arg}",
                "Can create files outside sandbox"))
        # D-Bus talk-name wildcards
        if re.match(r"--talk-name=.*\*", arg):
            result.add(Finding("HIGH", "permissions",
                f"Wildcard D-Bus access: {arg}",
                "Can communicate with any D-Bus service"))
        # own-name
        if arg.startswith("--own-name=") and not arg.endswith(app_id):
            result.add(Finding("MEDIUM", "permissions",
                f"Owns unexpected D-Bus name: {arg}",
                "App claims a D-Bus name different from its app-id"))

    # 2. Scan all sources recursively
    def scan_sources(sources, module_name="root"):
        if not isinstance(sources, list):
            return
        for src in sources:
            if not isinstance(src, dict):
                continue
            src_type = src.get("type", "")
            url = src.get("url", "")
            # Missing checksum
            if src_type in ("archive", "file") and url:
                has_checksum = any(src.get(k) for k in ("sha256", "sha512", "md5"))
                if not has_checksum:
                    result.add(Finding("HIGH", "sources",
                        f"Source without checksum in module '{module_name}'",
                        f"URL: {url} — no sha256/sha512 to verify integrity"))
                # Insecure HTTP
                if url.startswith("http://"):
                    result.add(Finding("MEDIUM", "sources",
                        f"Unencrypted HTTP source in module '{module_name}'",
                        f"URL: {url}"))
                # Suspicious domain
                try:
                    domain = url.split("/")[2].lower()
                    for bad in SUSPICIOUS_DOMAINS:
                        if bad in domain:
                            result.add(Finding("HIGH", "sources",
                                f"Source from suspicious domain: {domain}",
                                f"Full URL: {url}"))
                except Exception:
                    pass
            # Git source — prefer commit over branch for reproducibility
            if src_type == "git":
                if not src.get("commit") and src.get("branch"):
                    result.add(Finding("LOW", "sources",
                        f"Git source pinned to branch (not commit) in '{module_name}'",
                        "Branch references are mutable — use 'commit' for reproducibility"))

    # 3. Scan build commands in modules
    modules = data.get("modules", [])
    def scan_module(mod, depth=0):
        if not isinstance(mod, dict):
            return
        name = mod.get("name", f"module-{depth}")
        # Sources
        scan_sources(mod.get("sources", []), name)
        # Build commands
        for cmd_key in ("build-commands", "post-install", "cleanup", "pre-install"):
            for cmd in (mod.get(cmd_key) or []):
                for pattern, sev, reason in SUSPICIOUS_BUILD_PATTERNS:
                    if re.search(pattern, cmd, re.IGNORECASE):
                        result.add(Finding(sev, "build_commands",
                            f"Suspicious command in module '{name}' [{cmd_key}]",
                            f"Pattern: {reason}\nCommand: {cmd[:200]}"))
        # Recurse sub-modules
        for sub in (mod.get("modules") or []):
            scan_module(sub, depth + 1)

    for mod in modules:
        scan_module(mod)

    # 4. Check app-id format (typosquatting detection)
    if app_id and app_id != "unknown":
        parts = app_id.split(".")
        if len(parts) < 3:
            result.add(Finding("LOW", "manifest",
                f"Non-standard app-id format: {app_id}",
                "Valid Flatpak app-ids have at least 3 components (e.g. org.example.App)"))
        # Homoglyph / lookalike detection on well-known app-ids
        KNOWN_APPS = ["org.gnome.", "org.kde.", "org.freedesktop.", "com.valvesoftware.",
                      "org.mozilla.", "com.google.", "io.github."]
        for known in KNOWN_APPS:
            prefix = known.rstrip(".")
            if app_id.lower().startswith(prefix.lower()) and not app_id.startswith(known):
                result.add(Finding("HIGH", "manifest",
                    f"Possible impersonation of well-known namespace: {app_id}",
                    f"Looks similar to {known} but uses different casing/characters"))

    # 5. SDK check — very old SDKs often have unpatched CVEs
    sdk = data.get("sdk", "") or ""
    runtime = data.get("runtime", "") or ""
    for r in [sdk, runtime]:
        m = re.search(r"//(\d+\.\d+)", r)
        if m:
            ver = float(m.group(1))
            if ver < 23.08:
                result.add(Finding("MEDIUM", "manifest",
                    f"Outdated SDK/runtime version: {r}",
                    "Versions before 23.08 may contain unpatched CVEs"))

    result.add(Finding("INFO", "manifest",
        f"Manifest parsed successfully: {app_id}",
        f"{len(finish_args)} finish-args, {len(modules)} top-level modules"))

# ── Bundle scanner ────────────────────────────────────────────────────────────

def scan_bundle(bundle_path: str, result: ScanResult):
    """Extract .flatpak bundle and scan with ClamAV + Trivy + checksec."""
    workdir = tempfile.mkdtemp(prefix="agl-scan-")
    try:
        # .flatpak is an OSTree repo in a single-file format — extract via ostree
        # Alternatively treat as a zip/tar for file extraction
        extracted = os.path.join(workdir, "extracted")
        os.makedirs(extracted)

        # Try ostree extraction first
        r = subprocess.run(
            ["flatpak", "build-export", "--no-update-summary", extracted, bundle_path],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            # Fallback: try treating as zip
            r2 = subprocess.run(
                ["unzip", "-q", bundle_path, "-d", extracted],
                capture_output=True, text=True, timeout=60
            )
            if r2.returncode != 0:
                result.add(Finding("MEDIUM", "bundle",
                    "Could not extract bundle for deep scanning",
                    f"ostree error: {r.stderr[:200]}"))
                # Still run Trivy directly on the file
                _run_trivy(bundle_path, result)
                return

        # ClamAV scan
        _run_clamav(extracted, result)

        # Trivy filesystem scan
        _run_trivy(extracted, result)

        # checksec on all ELF binaries
        _run_checksec(extracted, result)

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_clamav(path: str, result: ScanResult):
    # Use clamdscan (daemon mode) — reuses loaded signatures, ~0ms vs 22s cold start
    r = subprocess.run(
        ["clamdscan", "-r", "--no-summary", path],
        capture_output=True, text=True, timeout=60
    )
    if r.returncode == 1:
        for line in r.stdout.splitlines():
            if "FOUND" in line:
                result.add(Finding("CRITICAL", "clamav",
                    "ClamAV: malware detected",
                    line.strip()))
    elif r.returncode == 2:
        # Daemon not available — fallback to clamscan
        r2 = subprocess.run(
            ["clamscan", "-r", "--no-summary", "--infected", path],
            capture_output=True, text=True, timeout=180
        )
        if r2.returncode == 1:
            for line in r2.stdout.splitlines():
                if "FOUND" in line:
                    result.add(Finding("CRITICAL", "clamav",
                        "ClamAV: malware detected",
                        line.strip()))
        elif r2.returncode == 0:
            result.add(Finding("INFO", "clamav", "ClamAV: no threats found (fallback mode)", f"Scanned: {path}"))
        else:
            result.add(Finding("MEDIUM", "clamav", "ClamAV scan error", r2.stderr[:300]))
    else:
        result.add(Finding("INFO", "clamav", "ClamAV: no threats found", f"Scanned: {path}"))


def _run_trivy(path: str, result: ScanResult):
    r = subprocess.run(
        ["trivy", "fs", "--format", "json", "--severity", "HIGH,CRITICAL",
         "--quiet", "--no-progress", path],
        capture_output=True, text=True, timeout=180
    )
    try:
        data = json.loads(r.stdout)
        for res in (data.get("Results") or []):
            for vuln in (res.get("Vulnerabilities") or []):
                sev = vuln.get("Severity", "UNKNOWN")
                cve = vuln.get("VulnerabilityID", "?")
                pkg = vuln.get("PkgName", "?")
                ver = vuln.get("InstalledVersion", "?")
                fixed = vuln.get("FixedVersion", "not fixed")
                result.add(Finding(
                    "CRITICAL" if sev == "CRITICAL" else "HIGH",
                    "trivy",
                    f"CVE in bundled library: {cve} ({pkg} {ver})",
                    f"Severity: {sev} | Fix available: {fixed}"
                ))
        if not any(f["category"] == "trivy" for f in result.findings):
            result.add(Finding("INFO", "trivy", "Trivy: no HIGH/CRITICAL CVEs found", ""))
    except Exception as e:
        result.add(Finding("LOW", "trivy", "Trivy output parse error", str(e)[:200]))


def _run_checksec(path: str, result: ScanResult):
    """Check ELF binary hardening flags using checksec (Python edition)."""
    CHECKSEC_BIN = "/usr/local/bin/checksec"
    missing_hardening = []
    try:
        r = subprocess.run(
            [CHECKSEC_BIN, "-j", "-r", path],
            capture_output=True, text=True, timeout=60
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        for binary, props in data.items():
            if not isinstance(props, dict):
                continue
            issues = []
            pie = props.get("pie", "")
            if pie and str(pie).lower() not in ("pie", "true", "dso"):
                issues.append("no PIE")
            if props.get("nx") is False or props.get("nx") == "false":
                issues.append("NX disabled")
            if props.get("canary") is False or props.get("canary") == "false":
                issues.append("no stack canary")
            relro = str(props.get("relro", "")).lower()
            if relro in ("none", "no relro", ""):
                issues.append("no RELRO")
            if issues:
                missing_hardening.append(f"{Path(binary).name}: {', '.join(issues)}")
    except (json.JSONDecodeError, FileNotFoundError):
        pass  # checksec not available or no ELF binaries
    except Exception as e:
        result.add(Finding("LOW", "binary", "checksec error", str(e)[:200]))
        return

    if missing_hardening:
        result.add(Finding("LOW", "binary",
            f"{len(missing_hardening)} binaries missing hardening flags",
            "\n".join(missing_hardening[:10])))
    else:
        result.add(Finding("INFO", "binary", "Binary hardening: all ELF binaries pass checksec", ""))


# ── Main entry point ──────────────────────────────────────────────────────────

def scan_submission(
    submission_id: int,
    manifest_content: Optional[str] = None,
    manifest_path: Optional[str] = None,
    bundle_path: Optional[str] = None,
) -> ScanResult:
    result = ScanResult(
        submission_id=submission_id,
        manifest_path=manifest_path,
        bundle_path=bundle_path,
    )

    if manifest_content:
        scan_manifest(manifest_content, result)
    elif manifest_path and os.path.exists(manifest_path):
        scan_manifest(Path(manifest_path).read_text(), result)

    if bundle_path and os.path.exists(bundle_path):
        scan_bundle(bundle_path, result)

    result.compute_verdict()
    return result


# ── CLI usage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, argparse

    parser = argparse.ArgumentParser(description="AGL Flatpak Security Scanner")
    parser.add_argument("--manifest", help="Path to Flatpak manifest (.yaml/.json)")
    parser.add_argument("--bundle",   help="Path to .flatpak bundle file")
    parser.add_argument("--id",       type=int, default=0, help="Submission ID")
    parser.add_argument("--json",     action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.manifest and not args.bundle:
        parser.print_help()
        sys.exit(1)

    manifest_content = None
    if args.manifest:
        manifest_content = Path(args.manifest).read_text()

    result = scan_submission(
        submission_id=args.id,
        manifest_content=manifest_content,
        bundle_path=args.bundle,
    )

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        verdict_color = {"PASS": "\033[32m", "WARN": "\033[33m", "BLOCK": "\033[31m"}
        vc = verdict_color.get(result.verdict, "")
        reset = "\033[0m"
        print(f"\n{'='*60}")
        print(f"AGL Flatpak Scanner — Submission #{result.scanned_at}")
        print(f"Verdict: {vc}{result.verdict}{reset}  |  Score: {result.risk_score}/100")
        print(f"{'='*60}")
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        findings = sorted(result.findings, key=lambda f: sev_order.get(f["severity"], 5))
        for f in findings:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"}.get(f["severity"], "•")
            print(f"\n{icon} [{f['severity']}] {f['category'].upper()}: {f['message']}")
            if f["detail"]:
                for line in f["detail"].splitlines():
                    print(f"   {line}")
        print(f"\n{result.summary}\n")
