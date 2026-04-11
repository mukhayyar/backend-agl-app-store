"""
Email service using Resend.
All transactional emails for PensHub App Store go through here.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_client():
    """Get configured Resend client, or None if not configured."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — email sending disabled")
        return None, None
    import resend
    resend.api_key = settings.resend_api_key
    return resend, settings.resend_from_email


def _send(to: str, subject: str, html: str) -> bool:
    """Send a single email. Returns True on success."""
    resend, from_email = _get_client()
    if resend is None:
        return False
    try:
        resend.Emails.send({
            "from": from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent: {subject!r} → {to}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


# ─── Templates ────────────────────────────────────────────────────────────────

def _base(title: str, body: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f5f5f5; margin: 0; padding: 24px; }}
    .card {{ background: #fff; border-radius: 12px; max-width: 560px;
             margin: 0 auto; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
    h1 {{ font-size: 22px; margin: 0 0 16px; color: #111; }}
    p  {{ font-size: 15px; line-height: 1.6; color: #444; margin: 0 0 12px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px;
              font-size: 13px; font-weight: 600; }}
    .green {{ background: #d1fae5; color: #065f46; }}
    .red   {{ background: #fee2e2; color: #991b1b; }}
    .blue  {{ background: #dbeafe; color: #1e40af; }}
    .mono  {{ font-family: monospace; font-size: 13px; background: #f3f4f6;
              padding: 8px 12px; border-radius: 6px; word-break: break-all; }}
    .footer {{ margin-top: 24px; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb;
               padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    {body}
    <div class="footer">PensHub App Store — <a href="https://agl-store.cyou">agl-store.cyou</a></div>
  </div>
</body>
</html>
"""


# ─── Email Functions ───────────────────────────────────────────────────────────

def send_welcome(to: str, display_name: str) -> bool:
    """Welcome email on first registration."""
    return _send(
        to=to,
        subject="Welcome to PensHub App Store!",
        html=_base(
            f"Welcome, {display_name}!",
            f"""
<p>Your PensHub developer account is ready.</p>
<p>You can now:</p>
<ul>
  <li>Browse the app catalog</li>
  <li>Generate a developer API key to submit your apps</li>
  <li>Track your app's install statistics</li>
</ul>
<p>Get started at <a href="https://backoffice.agl-store.cyou">backoffice.agl-store.cyou</a></p>
""",
        ),
    )


def send_api_key_created(to: str, key_name: str, key_prefix: str) -> bool:
    """Notify developer that a new API key was created."""
    return _send(
        to=to,
        subject=f"API Key Created: {key_name}",
        html=_base(
            "New API Key Generated",
            f"""
<p>A new developer API key has been created for your account.</p>
<p><strong>Name:</strong> {key_name}<br>
   <strong>Prefix:</strong> <span class="mono">{key_prefix}...</span></p>
<p>If you did not create this key, please revoke it immediately from your
   <a href="https://backoffice.agl-store.cyou/developer/keys">developer dashboard</a>.</p>
""",
        ),
    )


def send_app_submitted(to: str, app_name: str, app_id: str, submission_id: int) -> bool:
    """Confirm app submission to developer."""
    return _send(
        to=to,
        subject=f"App Submitted for Review: {app_name}",
        html=_base(
            "Your app is under review",
            f"""
<p>We've received your submission for <strong>{app_name}</strong>
   (<span class="mono">{app_id}</span>).</p>
<p><span class="badge blue">Submission #{submission_id}</span></p>
<p>Our team will review it and you'll get an email when a decision is made.
   This usually takes 1–3 business days.</p>
<p>You can track the status at
   <a href="https://backoffice.agl-store.cyou/developer/apps">My Apps</a>.</p>
""",
        ),
    )


def send_app_approved(to: str, app_name: str, app_id: str) -> bool:
    """Notify developer that their app was approved."""
    return _send(
        to=to,
        subject=f"App Approved: {app_name} 🎉",
        html=_base(
            "Your app is live!",
            f"""
<p><span class="badge green">Approved</span></p>
<p>Congratulations! <strong>{app_name}</strong> (<span class="mono">{app_id}</span>)
   has been approved and is now live on PensHub App Store.</p>
<p>Users can find and install it at
   <a href="https://agl-store.cyou/apps/{app_id}">agl-store.cyou/apps/{app_id}</a>.</p>
<p>Next steps: push a Flatpak build using your developer key to make the app installable.</p>
""",
        ),
    )


def send_app_rejected(to: str, app_name: str, app_id: str, reason: str) -> bool:
    """Notify developer that their app was rejected."""
    return _send(
        to=to,
        subject=f"App Submission Update: {app_name}",
        html=_base(
            "Submission not approved",
            f"""
<p><span class="badge red">Not Approved</span></p>
<p>Your submission for <strong>{app_name}</strong>
   (<span class="mono">{app_id}</span>) was not approved at this time.</p>
<p><strong>Reason:</strong></p>
<p class="mono">{reason}</p>
<p>You're welcome to address the feedback and
   <a href="https://backoffice.agl-store.cyou/developer/apps">resubmit</a>.</p>
""",
        ),
    )


def send_admin_new_submission(
    to: str,
    app_name: str,
    app_id: str,
    developer_name: str,
    submission_id: int,
) -> bool:
    """Notify admin of a new app submission."""
    return _send(
        to=to,
        subject=f"[PensHub] New App Submission: {app_name}",
        html=_base(
            "New App Submission",
            f"""
<p>A developer has submitted an app for review.</p>
<p><strong>App:</strong> {app_name} (<span class="mono">{app_id}</span>)<br>
   <strong>Developer:</strong> {developer_name}<br>
   <strong>Submission ID:</strong> #{submission_id}</p>
<p><a href="https://backoffice.agl-store.cyou/admin/submissions/{submission_id}">
   Review this submission →</a></p>
""",
        ),
    )
