#!/usr/bin/env python3
"""
Populate AppStream metadata for the AGL Store flat-manager OSTree repo.
"""

import sys
import os
import json
import gzip
import re
import urllib.request
import urllib.error
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# ── DB query ──────────────────────────────────────────────────────────────────
import subprocess

_db_url = os.environ.get("DATABASE_URL", "postgresql://pensagl:CHANGE_ME_DB_PASSWORD@localhost/agl_store")

PSQL_CMD = [
    "psql",
    _db_url,
    "-t", "-A", "-F", "\t",
    "-c",
    """
SELECT a.id, a.name, a.summary, a.description, a.developer_name, a.icon,
       string_agg(ac.category, ',') as categories
FROM apps a
LEFT JOIN app_categories ac ON ac.app_id = a.id
WHERE a.published = true AND (a.expires_at IS NULL OR a.expires_at > NOW())
GROUP BY a.id, a.name, a.summary, a.description, a.developer_name, a.icon
ORDER BY a.id
LIMIT 60;
"""
]

print("Querying database...")
result = subprocess.run(PSQL_CMD, capture_output=True, text=True)
if result.returncode != 0:
    print("DB error:", result.stderr)
    sys.exit(1)

apps = []
for line in result.stdout.strip().split("\n"):
    if not line.strip():
        continue
    parts = line.split("\t")
    if len(parts) < 7:
        # pad missing fields
        parts += [""] * (7 - len(parts))
    app_id, name, summary, description, developer_name, icon, categories_raw = parts[:7]
    categories = [c.strip() for c in categories_raw.split(",") if c.strip()] if categories_raw else []
    apps.append({
        "id": app_id.strip(),
        "name": name.strip(),
        "summary": summary.strip(),
        "description": description.strip(),
        "developer_name": developer_name.strip(),
        "icon": icon.strip(),
        "categories": categories,
    })

print(f"Found {len(apps)} published apps in DB.")

# ── Get GitHub folder list ────────────────────────────────────────────────────
print("Fetching GitHub repo tree...")
tree_url = "https://api.github.com/repos/mukhayyar/simple-flatpak-app-collections/git/trees/main"
req = urllib.request.Request(tree_url, headers={"User-Agent": "agl-store-appstream/1.0"})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        tree_data = json.loads(resp.read().decode())
    folders = [item["path"] for item in tree_data.get("tree", []) if item["type"] == "tree"]
    print(f"Found {len(folders)} folders in GitHub repo.")
except Exception as e:
    print(f"Warning: could not fetch GitHub tree: {e}")
    folders = []

def app_id_to_folder(app_id, folders):
    """
    com.pens.HashTool → find folder ending with '-hashtool' or '-hash-tool'
    Strategy: take last segment, lowercase, try to find folder suffix match.
    """
    suffix = app_id.split(".")[-1].lower()  # e.g. "hashtool"

    # Try exact suffix match first (folder ends with -<suffix>)
    for folder in folders:
        if folder.lower().endswith("-" + suffix):
            return folder

    # Try converting PascalCase to kebab: HashTool → hash-tool
    kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', app_id.split(".")[-1]).lower()
    for folder in folders:
        if folder.lower().endswith("-" + kebab.split("-")[-1]):
            # prefer exact kebab match
            if folder.lower().endswith(kebab):
                return folder
    for folder in folders:
        if folder.lower().endswith(kebab):
            return folder

    # Partial: folder contains kebab anywhere
    for folder in folders:
        if kebab in folder.lower():
            return folder

    # Last resort: suffix without dashes
    for folder in folders:
        folder_no_dash = folder.replace("-", "")
        if folder_no_dash.endswith(suffix):
            return folder

    return None

# ── Dirs ──────────────────────────────────────────────────────────────────────
ICONS_DIR = "/tmp/appstream-icons/128x128"
COMMIT_DIR = "/tmp/appstream-commit/icons/128x128"
os.makedirs(ICONS_DIR, exist_ok=True)
os.makedirs(COMMIT_DIR, exist_ok=True)
os.makedirs("/tmp/appstream-commit", exist_ok=True)

# ── Build AppStream XML ───────────────────────────────────────────────────────
print("Building AppStream XML...")
components_el = Element("components", version="0.14", origin="flatpak")

success_count = 0
missing_folders = []

for app in apps:
    app_id = app["id"]
    folder = app_id_to_folder(app_id, folders)

    if not folder:
        missing_folders.append(app_id)
        print(f"  WARNING: no folder found for {app_id}, using fallback icon URL")
        # Use a generic fallback
        last_part = app_id.split(".")[-1]
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', last_part).lower()
        folder = kebab  # won't resolve to real icon but XML will still be valid

    icon_url = f"https://raw.githubusercontent.com/mukhayyar/simple-flatpak-app-collections/main/{folder}/icon.png"

    comp = SubElement(components_el, "component", type="desktop-application")

    SubElement(comp, "id").text = app_id
    SubElement(comp, "name").text = app["name"] or app_id.split(".")[-1]
    SubElement(comp, "summary").text = app["summary"] or "No summary available."

    desc_el = SubElement(comp, "description")
    desc_text = app["description"] or app["summary"] or "No description available."
    SubElement(desc_el, "p").text = desc_text

    SubElement(comp, "icon", type="remote").text = icon_url

    if app["categories"]:
        cats_el = SubElement(comp, "categories")
        for cat in app["categories"]:
            SubElement(cats_el, "category").text = cat

    SubElement(comp, "url", type="homepage").text = "https://github.com/mukhayyar/simple-flatpak-app-collections"

    dev_el = SubElement(comp, "developer")
    SubElement(dev_el, "name").text = "PENS AGL Store"

    releases_el = SubElement(comp, "releases")
    SubElement(releases_el, "release", version="1.0.0", date="2026-04-11")

    SubElement(comp, "content_rating", type="oars-1.1")

    # Bundle element is arch-specific; we'll build two XML variants below
    SubElement(comp, "bundle",
               type="flatpak",
               runtime="org.gnome.Platform/{ARCH}/45",
               sdk="org.gnome.Sdk/{ARCH}/45").text = app_id

    success_count += 1

if missing_folders:
    print(f"  Apps without matched folders ({len(missing_folders)}): {missing_folders[:10]}{'...' if len(missing_folders) > 10 else ''}")

# Build per-arch XML variants
ARCHES = ["x86_64", "aarch64"]
arch_gz = {}

for _arch in ARCHES:
    _xml_str = minidom.parseString(
        tostring(components_el, encoding="unicode").replace("{ARCH}", _arch)
    ).toprettyxml(indent="  ")
    if _xml_str.startswith("<?xml"):
        _xml_str = _xml_str[_xml_str.index("\n")+1:]
    _xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n' + _xml_str

    _xml_path = f"/tmp/appstream-{_arch}.xml"
    _gz_path  = f"/tmp/appstream-{_arch}.xml.gz"
    with open(_xml_path, "w", encoding="utf-8") as f:
        f.write(_xml_out)
    with open(_xml_path, "rb") as f_in:
        with gzip.open(_gz_path, "wb") as f_out:
            f_out.write(f_in.read())
    arch_gz[_arch] = _gz_path
    print(f"Written {_gz_path} ({os.path.getsize(_gz_path)} bytes)")

# Keep backward-compat aliases
XML_PATH = "/tmp/appstream-x86_64.xml"
GZ_PATH  = arch_gz["x86_64"]

# ── Download icons ────────────────────────────────────────────────────────────
print("Downloading icons...")
icon_ok = 0
icon_fail = 0

for app in apps:
    app_id = app["id"]
    folder = app_id_to_folder(app_id, folders)
    if not folder:
        icon_fail += 1
        continue

    icon_url = f"https://raw.githubusercontent.com/mukhayyar/simple-flatpak-app-collections/main/{folder}/icon.png"
    out_path = f"{ICONS_DIR}/{app_id}.png"
    commit_path = f"{COMMIT_DIR}/{app_id}.png"

    try:
        req = urllib.request.Request(icon_url, headers={"User-Agent": "agl-store/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        with open(commit_path, "wb") as f:
            f.write(data)
        icon_ok += 1
    except Exception as e:
        print(f"  Icon fail {app_id}: {e}")
        icon_fail += 1

print(f"Icons: {icon_ok} ok, {icon_fail} failed")

# ── Prepare commit dir ────────────────────────────────────────────────────────
import shutil
shutil.copy(GZ_PATH, "/tmp/appstream-commit/appstream.xml.gz")
print("Prepared /tmp/appstream-commit/")
# aarch64 commit dir
os.makedirs("/tmp/appstream-commit-aarch64/icons/128x128", exist_ok=True)
import shutil as _sh2
# skip - icons copied separately below
shutil.copy(arch_gz["aarch64"], "/tmp/appstream-commit-aarch64/appstream.xml.gz")
# also copy icons
if os.path.isdir("/tmp/appstream-commit/icons"):
    _sh2.copytree("/tmp/appstream-commit/icons", "/tmp/appstream-commit-aarch64/icons", dirs_exist_ok=True)
print("Prepared /tmp/appstream-commit-aarch64/")

# ── OSTree commits ────────────────────────────────────────────────────────────
REPO = "/srv/flatpak-repo"

def run(cmd, check=True):
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print("   ", r.stdout.strip()[:500])
    if r.stderr.strip():
        print("   STDERR:", r.stderr.strip()[:500])
    if check and r.returncode != 0:
        print(f"FAILED (rc={r.returncode})")
        sys.exit(1)
    return r

for _arch, _commit_dir in [("x86_64", "/tmp/appstream-commit"), ("aarch64", "/tmp/appstream-commit-aarch64")]:
    print(f"\nCommitting to OSTree appstream/{_arch}...")
    run([
        "ostree", "commit",
        f"--repo={REPO}",
        f"--branch=appstream/{_arch}",
        f"--tree=dir={_commit_dir}",
        "--timestamp=2026-04-11T00:00:00Z",
        "--no-bindings",
    ])
    print(f"Committing to OSTree appstream2/{_arch}...")
    run([
        "ostree", "commit",
        f"--repo={REPO}",
        f"--branch=appstream2/{_arch}",
        f"--tree=dir={_commit_dir}",
        "--timestamp=2026-04-11T00:00:00Z",
        "--no-bindings",
    ])

print("\nUpdating repo summary...")
run([
    "flatpak", "build-update-repo",
    "--no-update-appstream",
    REPO,
])

print("\nCopying appstream.xml.gz to served locations...")
for _arch, _gz in arch_gz.items():
    _dst_dir = f"{REPO}/appstream/{_arch}"
    os.makedirs(_dst_dir, exist_ok=True)
    shutil.copy(_gz, f"{_dst_dir}/appstream.xml.gz")
    print(f"Copied to {_dst_dir}/appstream.xml.gz")
    # also copy icons
    _icon_src = f"/tmp/appstream-icons/128x128"
    _icon_dst = f"{_dst_dir}/icons/128x128"
    if os.path.isdir(_icon_src):
        os.makedirs(_icon_dst, exist_ok=True)
        for _ic in os.listdir(_icon_src):
            shutil.copy2(f"{_icon_src}/{_ic}", f"{_icon_dst}/{_ic}")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\nVerifying...")
with gzip.open(GZ_PATH, "rb") as f:
    _verify_content = f.read().decode("utf-8")
component_count = _verify_content.count("<component")
print(f"Components in appstream.xml.gz: {component_count}")

print(f"\n✓ Done. {success_count} components written to AppStream XML for x86_64 + aarch64.")
print(f"  OSTree branches: appstream/x86_64, appstream2/x86_64, appstream/aarch64, appstream2/aarch64")
