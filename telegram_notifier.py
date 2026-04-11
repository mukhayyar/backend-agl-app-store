"""
AGL App Store — Telegram Notifier
Sends structured alerts to the developer via @PensHubStoreBot.
"""
import os, json, urllib.request, urllib.parse, logging, textwrap
from typing import Optional

log = logging.getLogger(__name__)

BOT_TOKEN    = os.getenv("PENSSTORE_BOT_TOKEN", "")
DEVELOPER_CHAT_ID = os.getenv("PENSSTORE_DEVELOPER_CHAT_ID", "")

# Severity → emoji
SEV_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"}
VERDICT_ICON = {"BLOCK": "🚫", "WARN": "⚠️", "PASS": "✅", "NOT_SCANNED": "🔍"}


def _send(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Low-level send. Returns True on success."""
    if not BOT_TOKEN or not chat_id:
        log.warning("Telegram: BOT_TOKEN or chat_id not set — skipping alert")
        return False
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def notify_developer(text: str) -> bool:
    return _send(DEVELOPER_CHAT_ID, text)


# ── Alert templates ───────────────────────────────────────────────────────────

def alert_new_submission(submission_id: int, app_name: str, developer: str):
    notify_developer(
        f"📥 <b>New App Submission</b>\n"
        f"App: <code>{app_name}</code>\n"
        f"Developer: {developer}\n"
        f"ID: #{submission_id}\n"
        f"<a href='https://admin.agl-store.cyou/admin/submissions/{submission_id}'>Review →</a>"
    )


def alert_scan_result(submission_id: int, app_name: str, result: dict):
    verdict   = result.get("verdict", "UNKNOWN")
    score     = result.get("risk_score", 0)
    summary   = result.get("summary", "")
    findings  = result.get("findings", [])
    icon      = VERDICT_ICON.get(verdict, "❓")

    # Top 3 most severe findings
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    top = sorted(findings, key=lambda f: sev_order.get(f.get("severity", "INFO"), 5))[:3]
    finding_lines = "\n".join(
        f"{SEV_ICON.get(f['severity'], '•')} {f['message']}"
        for f in top
    )

    notify_developer(
        f"{icon} <b>Scan Result: {verdict}</b> — {app_name}\n"
        f"Score: <b>{score}/100</b> | #{submission_id}\n\n"
        f"{finding_lines}\n\n"
        f"<i>{summary}</i>\n"
        f"<a href='https://admin.agl-store.cyou/admin/submissions/{submission_id}'>View submission →</a>"
    )


def alert_submission_approved(submission_id: int, app_name: str, app_id: str):
    notify_developer(
        f"✅ <b>App Approved</b>\n"
        f"<code>{app_name}</code> (<code>{app_id}</code>) is now live on the store.\n"
        f"Submission: #{submission_id}"
    )


def alert_submission_rejected(submission_id: int, app_name: str, reason: str):
    notify_developer(
        f"❌ <b>App Rejected</b>\n"
        f"<code>{app_name}</code> — Submission #{submission_id}\n"
        f"Reason: {reason[:200]}"
    )


def alert_app_expiring(app_name: str, app_id: str, days_left: int):
    urgency = "🔴" if days_left <= 7 else "🟡"
    notify_developer(
        f"{urgency} <b>App Certificate Expiring</b>\n"
        f"<code>{app_name}</code> (<code>{app_id}</code>)\n"
        f"Expires in <b>{days_left} days</b>.\n"
        f"<a href='https://admin.agl-store.cyou/developer/portal'>Renew →</a>"
    )


def alert_app_expired(app_name: str, app_id: str):
    notify_developer(
        f"🚫 <b>App Unpublished — Certificate Expired</b>\n"
        f"<code>{app_name}</code> (<code>{app_id}</code>) has been taken offline.\n"
        f"<a href='https://admin.agl-store.cyou/developer/portal'>Renew certificate →</a>"
    )


def alert_publisher_key_expiring(days_left: int):
    urgency = "🔴" if days_left <= 7 else "🟡"
    notify_developer(
        f"{urgency} <b>Publisher Signing Key Expiring</b>\n"
        f"Your trusted publisher GPG key expires in <b>{days_left} days</b>.\n"
        f"All your verified apps will lose the ✓ badge when it expires.\n"
        f"<a href='https://admin.agl-store.cyou/developer/portal'>Renew →</a>"
    )


def alert_new_user_registered(display_name: str, email: str, is_org: bool, domain: Optional[str] = None):
    tag = f"🏢 <b>Organization</b> ({domain})" if is_org else "👤 Personal"
    notify_developer(
        f"🆕 <b>New Registration</b>\n"
        f"Name: {display_name}\n"
        f"Email: <code>{email}</code>\n"
        f"Type: {tag}"
    )


def alert_scan_blocked(submission_id: int, app_name: str, critical_count: int):
    notify_developer(
        f"🚫 <b>Submission Blocked by Scanner</b>\n"
        f"<code>{app_name}</code> — Submission #{submission_id}\n"
        f"<b>{critical_count} critical</b> security issue(s) found.\n"
        f"Auto-blocked — manual review required.\n"
        f"<a href='https://admin.agl-store.cyou/admin/submissions/{submission_id}'>Review →</a>"
    )
