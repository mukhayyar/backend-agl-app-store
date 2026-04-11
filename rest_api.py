"""
AGL App Store — FastAPI REST API
Runs alongside the gRPC server on port 8002.
Provides REST endpoints for the web frontend, admin backoffice,
and the developer publishing key workflow.
"""

import os, subprocess, shutil, tempfile, urllib.parse, urllib.request
import bcrypt, datetime, secrets, hashlib
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
import jwt as pyjwt
import httpx
from sqlalchemy.orm import Session
from database import (
    SessionLocal, engine, Base, App, User, Category,
    ConnectedAccount, UserRole, DeveloperToken, AppSubmission, DeveloperGpgKey
)

# ── Bootstrap ──────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AGL App Store API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────────────────────────
FLAT_MANAGER_SECRET = os.getenv("FLAT_MANAGER_SECRET", "CHANGE_ME_FLAT_MANAGER_SECRET")
FLAT_MANAGER_URL = os.getenv("FLAT_MANAGER_URL", "https://hub.agl-store.cyou")
API_SECRET = os.getenv("API_SECRET", "agl-api-secret-change-me")
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "agl-jwt-secret-change-me-in-production-use-64-chars")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://admin.agl-store.cyou")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
import sys
sys.path.insert(0, os.path.dirname(__file__))
from telegram_notifier import (
    notify_developer, alert_new_submission, alert_scan_result,
    alert_submission_approved, alert_submission_rejected,
    alert_app_expiring, alert_app_expired, alert_publisher_key_expiring,
    alert_new_user_registered, alert_scan_blocked,
)
from scan_queue import init_worker as _init_scan_worker, enqueue_scan as _enqueue_scan, ScanJob
from repo_watcher import init_repo_watcher, watch_app as _watch_app
from flatpak_scanner import scan_submission as _scan_flatpak, asdict as _asdict

RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
GENTOKEN_BIN = "/usr/local/bin/gentoken"
_TOKEN_PREFIX = "penshub_"

# ── DB Dependency ──────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Auth helpers ───────────────────────────────────────────────────────────
def require_admin_key(x_api_key: str = Header(None)):
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

def _create_jwt(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=JWT_EXPIRE_DAYS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_jwt(token: str) -> dict:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Known free/personal email providers (non-exhaustive but covers >99% of cases)
_FREE_EMAIL_DOMAINS = {
    "gmail.com","googlemail.com","yahoo.com","yahoo.co.uk","yahoo.co.jp","yahoo.fr",
    "yahoo.de","yahoo.es","yahoo.it","yahoo.com.br","yahoo.com.au","yahoo.com.ar",
    "hotmail.com","hotmail.co.uk","hotmail.fr","hotmail.de","hotmail.es","hotmail.it",
    "outlook.com","outlook.co.uk","outlook.fr","outlook.de","outlook.jp","live.com",
    "live.co.uk","live.fr","msn.com","icloud.com","me.com","mac.com",
    "aol.com","aim.com","protonmail.com","proton.me","tutanota.com","tutamail.com",
    "zoho.com","yandex.com","yandex.ru","mail.ru","inbox.ru","list.ru","bk.ru",
    "gmx.com","gmx.de","gmx.net","web.de","t-online.de","freenet.de",
    "qq.com","163.com","126.com","sina.com","foxmail.com",
    "naver.com","daum.net","hanmail.net",
    "rocketmail.com","ymail.com","maildrop.cc","guerrillamail.com",
    "mailinator.com","throwam.com","tempmail.com","10minutemail.com",
    "sharklasers.com","guerrillamailblock.com","grr.la","guerrillamail.info",
    "dispostable.com","mailnull.com","spamgourmet.com","trashmail.com",
}

def _is_organization_email(email: str) -> tuple[bool, str]:
    """Returns (is_org, domain). Org = not a known free provider."""
    if not email or "@" not in email:
        return False, ""
    domain = email.rsplit("@", 1)[1].lower().strip()
    is_org = domain not in _FREE_EMAIL_DOMAINS
    return is_org, domain

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def _get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = _decode_jwt(token)
    except HTTPException:
        return None
    return db.query(User).filter(User.id == payload["user_id"]).first()

def _require_jwt_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.split(" ", 1)[1]
    payload = _decode_jwt(token)
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def _require_jwt_admin(user: User = Depends(_require_jwt_user)) -> User:
    if getattr(user, "role", "user") not in ("admin", "reviewer"):
        raise HTTPException(status_code=403, detail="Admin or reviewer access required")
    return user

def _get_dev_user(
    x_developer_key: str = Header(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Accept either X-Developer-Key or Bearer JWT."""
    if x_developer_key:
        token_hash = _hash_token(x_developer_key)
        record = db.query(DeveloperToken).filter(
            DeveloperToken.token_hash == token_hash,
            DeveloperToken.is_active == True,
        ).first()
        if not record:
            raise HTTPException(status_code=401, detail="Invalid developer key")
        if record.expires_at and record.expires_at < datetime.datetime.utcnow():
            raise HTTPException(status_code=401, detail="Developer key expired")
        record.last_used_at = datetime.datetime.utcnow()
        db.commit()
        return record.user
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        payload = _decode_jwt(token)
        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if user:
            return user
    raise HTTPException(status_code=401, detail="Authentication required (Bearer or X-Developer-Key)")

def _get_user_email(db: Session, user_id: int) -> Optional[str]:
    acc = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_id,
        ConnectedAccount.email != None,
    ).order_by(ConnectedAccount.last_used.desc()).first()
    return acc.email if acc else None

# ── Email (Resend) ─────────────────────────────────────────────────────────
def _send_email(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        return False
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({"from": RESEND_FROM, "to": [to], "subject": subject, "html": html})
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

def _email_welcome(to: str, name: str):
    _send_email(to, "Welcome to PensHub App Store!",
        f"<p>Hi {name}!</p><p>Your PensHub developer account is ready. "
        f"Go to <a href='https://admin.agl-store.cyou'>admin.agl-store.cyou</a> to get started.</p>")

def _email_key_created(to: str, key_name: str, prefix: str):
    _send_email(to, f"API Key Created: {key_name}",
        f"<p>A new developer API key <b>{key_name}</b> (<code>{prefix}...</code>) was created for your account.</p>"
        f"<p>If you didn't do this, revoke it immediately.</p>")

def _email_submitted(to: str, app_name: str, app_id: str, sub_id: int):
    _send_email(to, f"App Submitted: {app_name}",
        f"<p>Your app <b>{app_name}</b> (<code>{app_id}</code>) has been submitted for review (#{sub_id}).</p>"
        f"<p>You'll receive an email when it's reviewed.</p>")

def _email_approved(to: str, app_name: str, app_id: str):
    _send_email(to, f"App Approved: {app_name} 🎉",
        f"<p>🎉 Congratulations! <b>{app_name}</b> (<code>{app_id}</code>) is now live on PensHub!</p>"
        f"<p>View it at <a href='https://agl-store.cyou/apps/{app_id}'>agl-store.cyou/apps/{app_id}</a></p>")

def _email_rejected(to: str, app_name: str, app_id: str, reason: str):
    _send_email(to, f"App Submission Update: {app_name}",
        f"<p>Your submission for <b>{app_name}</b> (<code>{app_id}</code>) was not approved.</p>"
        f"<p><b>Reason:</b> {reason}</p>"
        f"<p>You're welcome to fix the issues and resubmit.</p>")

def _email_admin_new_sub(app_name: str, app_id: str, dev_name: str, sub_id: int):
    if ADMIN_EMAIL:
        _send_email(ADMIN_EMAIL, f"[PensHub] New Submission: {app_name}",
            f"<p>New app submission: <b>{app_name}</b> (<code>{app_id}</code>) by {dev_name}. "
            f"Submission #{sub_id}.</p>"
            f"<p><a href='https://admin.agl-store.cyou/admin/submissions/{sub_id}'>Review →</a></p>")

# ── Pydantic schemas ───────────────────────────────────────────────────────
class AppOut(BaseModel):
    id: str
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    developer_name: Optional[str] = None
    icon: Optional[str] = None
    type: Optional[str] = None
    runtime: Optional[str] = None
    project_license: Optional[str] = None
    is_free_license: Optional[bool] = None
    is_mobile_friendly: Optional[bool] = None
    updated_at: Optional[datetime.datetime] = None
    added_at: Optional[datetime.datetime] = None
    categories: List[str] = []
    screenshots: List[dict] = []
    homepage: Optional[str] = None
    published: bool = True
    expires_at: Optional[datetime.datetime] = None
    gpg_fingerprint: Optional[str] = None
    gpg_uid: Optional[str] = None
    is_verified: bool = False
    class Config:
        from_attributes = True

class IssueTokenRequest(BaseModel):
    developer_name: str
    role: str = "developer"
    app_id: Optional[str] = None
    is_trial: bool = False

class RegisterAppRequest(BaseModel):
    app_id: str
    developer_name: str
    developer_email: Optional[str] = None

class GithubLoginRequest(BaseModel):
    access_token: str

class ScreenshotIn(BaseModel):
    url: str
    caption: Optional[str] = None

class SubmitAppRequest(BaseModel):
    app_id: str
    name: str
    summary: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None
    app_type: str = "desktop-application"
    categories: List[str] = []
    tags: List[str] = []
    screenshots: List[ScreenshotIn] = []

    @field_validator("categories")
    @classmethod
    def categories_required(cls, v):
        cats = [c.strip() for c in v if c.strip()]
        if not cats:
            raise ValueError("At least one category is required")
        return cats

    @field_validator("tags")
    @classmethod
    def tags_required(cls, v):
        tags = [t.strip().lower() for t in v if t.strip()]
        if not tags:
            raise ValueError("At least one tag is required")
        if len(tags) > 10:
            raise ValueError("Maximum 10 tags allowed")
        for t in tags:
            if len(t) > 32:
                raise ValueError(f"Tag '{t}' exceeds 32 characters")
        return tags

class CreateKeyRequest(BaseModel):
    name: str

class RejectRequest(BaseModel):
    reason: str


class UnpublishRequest(BaseModel):
    reason: str

class ExtendRequest(BaseModel):
    days: int = 365


def _email_expiry_reminder(to: str, app_name: str, app_id: str, days_left: int):
    renew_url = "https://admin.agl-store.cyou/developer/portal"
    _send_email(to, f"Action Required: {app_name} expiring in {days_left} days",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#b45309'>Warning: {app_name} Expiring Soon</h2>"
        f"<p>Your app <strong>{app_name}</strong> (<code>{app_id}</code>) on PensHub will expire "
        f"in <strong>{days_left} days</strong>. When it expires it will be automatically unpublished.</p>"
        f"<a href='{renew_url}' style='display:inline-block;background:#4f46e5;color:#fff;"
        f"padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0'>"
        f"Renew App</a></div>")

def _email_app_expired(to: str, app_name: str, app_id: str):
    renew_url = "https://admin.agl-store.cyou/developer/portal"
    _send_email(to, f"App Unpublished: {app_name} - Renewal Required",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#dc2626'>{app_name} Has Been Unpublished</h2>"
        f"<p>Your app <strong>{app_name}</strong> (<code>{app_id}</code>) signing certificate expired. "
        f"It has been automatically removed from PensHub to protect users.</p>"
        f"<a href='{renew_url}' style='display:inline-block;background:#4f46e5;color:#fff;"
        f"padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0'>"
        f"Renew Now</a></div>")

def _email_app_renewed(to: str, app_name: str, app_id: str, new_expiry: str):
    _send_email(to, f"App Renewed: {app_name}",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#16a34a'>{app_name} Successfully Renewed</h2>"
        f"<p>Your app <strong>{app_name}</strong> (<code>{app_id}</code>) has a new signing certificate.</p>"
        f"<p><strong>New expiry:</strong> {new_expiry}</p>"
        f"<p>You will receive reminders 30 and 7 days before expiry.</p></div>")

def _email_app_unpublished_admin(to: str, app_name: str, app_id: str, reason: str):
    _send_email(to, f"App Unpublished by Admin: {app_name}",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#dc2626'>{app_name} Unpublished</h2>"
        f"<p>Your app <strong>{app_name}</strong> (<code>{app_id}</code>) was unpublished by an admin.</p>"
        f"<p><strong>Reason:</strong> {reason}</p>"
        f"<p>Contact <a href='mailto:admin@agl-store.cyou'>admin@agl-store.cyou</a> to appeal.</p></div>")



def _email_trusted_publisher(to: str, name: str, fingerprint: str, expires: str):
    _send_email(to, "You are now a Trusted Publisher on PensHub",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#16a34a'>Congratulations, {name}! You are a Trusted Publisher</h2>"
        f"<p>Your developer account has been verified by the PensHub team. Your apps will now show "
        f"a <strong>Verified</strong> badge in the store, giving users confidence in your software.</p>"
        f"<h3>Your Personal Signing Key</h3>"
        f"<ul><li><strong>Fingerprint:</strong> <code>{fingerprint}</code></li>"
        f"<li><strong>Expires:</strong> {expires}</li></ul>"
        f"<p>Keep your signing key active by renewing it before it expires at "
        f"<a href='https://admin.agl-store.cyou/developer/portal'>Developer Portal</a>.</p></div>")

def _email_publisher_key_expired(to: str, name: str):
    _send_email(to, "Publisher Key Expired — Renew to Keep Verified Status",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2 style='color:#dc2626'>Publisher Signing Key Expired</h2>"
        f"<p>Hi {name}, your personal publisher signing key has expired. "
        f"Your apps will lose the Verified badge until you renew your key.</p>"
        f"<a href='https://admin.agl-store.cyou/developer/portal' style='display:inline-block;"
        f"background:#4f46e5;color:#fff;padding:12px 24px;border-radius:8px;"
        f"text-decoration:none;font-weight:600;margin:16px 0'>Renew Key</a></div>")

def _generate_gpg_key(app_id: str, app_name: str, developer_name: str, expire_years: int = 1, expire_days: Optional[int] = None):
    """Generate a GPG key for an app. Returns (fingerprint, public_key_armored, gpg_uid)."""
    gpg_home = tempfile.mkdtemp(prefix="penshub_gpg_")
    uid_email = f"app+{app_id.replace('.', '-')}@agl-store.cyou"
    uid_name = f"{app_name} (PensHub)"
    _days = expire_days if expire_days is not None else 365 * expire_years
    expire_date = (datetime.datetime.utcnow() + datetime.timedelta(days=_days)).strftime("%Y-%m-%d")
    batch = (
        "%no-protection\n"
        "Key-Type: RSA\n"
        "Key-Length: 4096\n"
        "Subkey-Type: RSA\n"
        "Subkey-Length: 4096\n"
        f"Name-Real: {uid_name}\n"
        f"Name-Email: {uid_email}\n"
        f"Expire-Date: {expire_date}\n"
        "%commit\n"
    )
    try:
        env = {**os.environ, "GNUPGHOME": gpg_home}
        batch_file = os.path.join(gpg_home, "keygen.batch")
        with open(batch_file, "w") as f:
            f.write(batch)
        r = subprocess.run(["gpg", "--batch", "--gen-key", batch_file],
            env=env, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"GPG keygen failed: {r.stderr}")
        fp_r = subprocess.run(["gpg", "--with-colons", "--fingerprint", uid_email],
            env=env, capture_output=True, text=True, timeout=10)
        fingerprint = ""
        for line in fp_r.stdout.splitlines():
            if line.startswith("fpr:"):
                fingerprint = line.split(":")[9]
                break
        exp_r = subprocess.run(["gpg", "--armor", "--export", uid_email],
            env=env, capture_output=True, text=True, timeout=10)
        return fingerprint, exp_r.stdout, f"{uid_name} <{uid_email}>"
    finally:
        shutil.rmtree(gpg_home, ignore_errors=True)


class EmailRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class EmailLoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    token: str

# ── Health ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup():
    """Initialize background workers on FastAPI startup."""
    _init_scan_worker(get_db, App, AppSubmission)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agl-app-store-api", "version": "2.0.0"}

# ── Apps ───────────────────────────────────────────────────────────────────
@app.get("/apps", response_model=List[AppOut])
def list_apps(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(App)
    # Only show published, non-expired apps
    q = q.filter(App.published == True)
    _now = datetime.datetime.utcnow()
    q = q.filter((App.expires_at == None) | (App.expires_at > _now))
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(App.name.ilike(like) | App.summary.ilike(like) | App.description.ilike(like) | App.developer_name.ilike(like))
    if category:
        q = q.filter(App.categories.any(Category.name == category))
    apps_list = q.order_by(App.updated_at.desc()).offset(offset).limit(limit).all()
    result = []
    for a in apps_list:
        shots = []
        for sc in a.screenshots:
            shots.append({"id": sc.id, "caption": sc.caption, "sizes": [{"src": sz.src, "width": sz.width, "height": sz.height} for sz in sc.sizes]})
        result.append(AppOut(
            id=a.id, name=a.name, summary=a.summary,
            description=a.description, developer_name=a.developer_name,
            icon=a.icon, type=a.type, runtime=a.runtime,
            project_license=a.project_license,
            is_free_license=a.is_free_license,
            is_mobile_friendly=a.is_mobile_friendly,
            updated_at=a.updated_at, added_at=a.added_at,
            categories=[c.name for c in a.categories],
            screenshots=shots,
            homepage=a.verification_website,
            published=a.published,
            expires_at=a.expires_at,
            gpg_fingerprint=a.gpg_fingerprint,
            gpg_uid=a.gpg_uid,
            is_verified=bool(a.is_verified),
        ))
    return result

@app.get("/apps/{app_id}", response_model=AppOut)
def get_app(app_id: str, db: Session = Depends(get_db)):
    a = db.query(App).filter(App.id == app_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="App not found")
    shots = []
    for sc in a.screenshots:
        shots.append({"id": sc.id, "caption": sc.caption, "sizes": [{"src": sz.src, "width": sz.width, "height": sz.height} for sz in sc.sizes]})
    return AppOut(
        id=a.id, name=a.name, summary=a.summary,
        description=a.description, developer_name=a.developer_name,
        icon=a.icon, type=a.type, runtime=a.runtime,
        project_license=a.project_license,
        is_free_license=a.is_free_license,
        is_mobile_friendly=a.is_mobile_friendly,
        updated_at=a.updated_at, added_at=a.added_at,
        categories=[c.name for c in a.categories],
        screenshots=shots,
        homepage=a.verification_website,
        published=a.published,
        expires_at=a.expires_at,
        gpg_fingerprint=a.gpg_fingerprint,
        gpg_uid=a.gpg_uid,
        is_verified=bool(a.is_verified),
    )

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).all()
    return [{"name": c.name, "description": c.description} for c in cats]

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return {
        "total_apps": db.query(App).filter(App.published == True).count(),
        "total_users": db.query(User).count(),
        "total_categories": db.query(Category).count(),
    }

# ── Auth: GitHub OAuth ─────────────────────────────────────────────────────

# ── Auth: Email/Password ──────────────────────────────────────────────────

def _send_verification_email(to: str, name: str, token: str):
    verify_url = f"https://admin.agl-store.cyou/verify-email?token={token}"
    _send_email(to, "Verify your PensHub account",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2>Verify your email</h2>"
        f"<p>Hi {name or 'there'}, click below to verify your PensHub account:</p>"
        f"<a href='{verify_url}' style='display:inline-block;background:#4f46e5;color:#fff;"
        f"padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0'>"
        f"Verify Email</a>"
        f"<p style='color:#6b7280;font-size:14px'>Or copy this link: {verify_url}</p>"
        f"<p style='color:#6b7280;font-size:12px'>This link expires in 24 hours. If you didn't register, ignore this email.</p>"
        f"</div>")

def _send_reset_email(to: str, name: str, token: str):
    reset_url = f"https://admin.agl-store.cyou/reset-password?token={token}"
    _send_email(to, "Reset your PensHub password",
        f"<div style='font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px'>"
        f"<h2>Reset your password</h2>"
        f"<p>Hi {name or 'there'}, click below to reset your PensHub password:</p>"
        f"<a href='{reset_url}' style='display:inline-block;background:#4f46e5;color:#fff;"
        f"padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0'>"
        f"Reset Password</a>"
        f"<p style='color:#6b7280;font-size:14px'>Or copy: {reset_url}</p>"
        f"<p style='color:#6b7280;font-size:12px'>This link expires in 1 hour. If you didn't request this, ignore it.</p>"
        f"</div>")

@app.post("/auth/register", status_code=201)
def register_email(body: EmailRegisterRequest, db: Session = Depends(get_db)):
    """Register a new account with email and password."""
    email = body.email.lower().strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email address")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    # Check if email already registered
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    is_org, domain = _is_organization_email(email)
    display_name = body.display_name or email.split("@")[0]
    verification_token = secrets.token_urlsafe(32)
    now = datetime.datetime.utcnow()
    user = User(
        email=email,
        password_hash=_hash_password(body.password),
        display_name=display_name,
        invite_code=secrets.token_urlsafe(8),
        auth_provider="email",
        email_verified=False,
        email_verification_token=verification_token,
        email_verification_expires=now + datetime.timedelta(hours=24),
        is_organization_email=is_org,
        organization_domain=domain if is_org else None,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _send_verification_email(email, display_name, verification_token)
    # [HOOK] notify new registration
    try:
        alert_new_user_registered(display_name, email, is_org, domain if is_org else None)
    except Exception: pass
    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "user_id": user.id,
        "email": email,
        "is_organization_email": is_org,
        "organization_domain": domain if is_org else None,
        "email_verified": False,
    }

@app.post("/auth/verify-email")
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    user = db.query(User).filter(User.email_verification_token == body.token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid or expired verification token")
    if user.email_verification_expires and user.email_verification_expires < now:
        raise HTTPException(status_code=400, detail="Verification token expired. Request a new one.")
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()
    token = _create_jwt(user.id, getattr(user, "role", "user"))
    return {
        "message": "Email verified successfully",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": getattr(user, "role", "user"),
    }

@app.post("/auth/resend-verification")
def resend_verification(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or user.auth_provider != "email":
        # Return 200 always to avoid enumeration
        return {"message": "If that email is registered and unverified, a new verification link has been sent."}
    if user.email_verified:
        return {"message": "Email already verified."}
    now = datetime.datetime.utcnow()
    user.email_verification_token = secrets.token_urlsafe(32)
    user.email_verification_expires = now + datetime.timedelta(hours=24)
    db.commit()
    _send_verification_email(user.email, user.display_name or "", user.email_verification_token)
    return {"message": "If that email is registered and unverified, a new verification link has been sent."}

@app.post("/auth/login/email")
def login_email(body: EmailLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Check your inbox for a verification link.")
    token = _create_jwt(user.id, getattr(user, "role", "user"))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": getattr(user, "role", "user"),
        "is_new": False,
        "is_organization_email": bool(user.is_organization_email),
        "organization_domain": user.organization_domain,
    }

@app.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    # Always return 200 to avoid enumeration
    if user and user.auth_provider == "email" and user.email_verified:
        now = datetime.datetime.utcnow()
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_expires = now + datetime.timedelta(hours=1)
        db.commit()
        _send_reset_email(user.email, user.display_name or "", user.password_reset_token)
    return {"message": "If that email has an account, a password reset link has been sent."}

@app.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    now = datetime.datetime.utcnow()
    user = db.query(User).filter(User.password_reset_token == body.token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid or expired reset token")
    if user.password_reset_expires and user.password_reset_expires < now:
        raise HTTPException(status_code=400, detail="Reset token expired. Request a new one.")
    user.password_hash = _hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    return {"message": "Password reset successfully. You can now log in."}

@app.get("/auth/check-email")
def check_email(email: str = Query(...)):
    """Public endpoint: check if an email is from an organization."""
    email = email.lower().strip()
    is_org, domain = _is_organization_email(email)
    return {
        "email": email,
        "is_organization_email": is_org,
        "organization_domain": domain if is_org else None,
        "account_type": "organization" if is_org else "personal",
    }

@app.get("/auth/methods")
def auth_methods():
    return {"methods": [{"method": "github", "name": "GitHub"}, {"method": "email", "name": "Email"}]}

@app.post("/auth/login")
async def login_github(body: GithubLoginRequest, db: Session = Depends(get_db)):
    """Login with a GitHub OAuth access_token. Creates account on first login."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://api.github.com/user",
            headers={"Authorization": f"Bearer {body.access_token}", "Accept": "application/json"})
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid GitHub token")
    data = resp.json()
    provider_id = data.get("id")
    if not provider_id:
        raise HTTPException(status_code=401, detail="Could not identify GitHub user")

    login = data.get("login", "")
    display_name = data.get("name") or login
    email = data.get("email", "")
    avatar_url = data.get("avatar_url", "")

    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.provider == "github",
        ConnectedAccount.provider_user_id == provider_id,
    ).first()

    is_new = False
    if account:
        user = account.user
        account.last_used = datetime.datetime.utcnow()
        db.commit()
    else:
        is_new = True
        user = User(
            display_name=display_name,
            invite_code=secrets.token_urlsafe(8),
            default_account_provider="github",
            default_account_login=login,
            role="user",
        )
        db.add(user)
        db.flush()
        account = ConnectedAccount(
            user_id=user.id,
            provider="github",
            provider_user_id=provider_id,
            login=login,
            avatar_url=avatar_url,
            display_name=display_name,
            email=email,
            last_used=datetime.datetime.utcnow(),
        )
        db.add(account)
        db.commit()
        db.refresh(user)
        if email:
            _email_welcome(email, display_name)

    token = _create_jwt(user.id, getattr(user, "role", "user"))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": getattr(user, "role", "user"),
        "is_new": is_new,
    }

@app.get("/auth/user")
def get_auth_user(user: User = Depends(_require_jwt_user), db: Session = Depends(get_db)):
    email = user.email or _get_user_email(db, user.id)
    return {
        "id": user.id,
        "display_name": user.display_name,
        "role": getattr(user, "role", "user"),
        "email": email,
        "accepted_publisher_agreement": bool(user.accepted_publisher_agreement_at),
        "default_account_provider": user.default_account_provider,
        "default_account_login": user.default_account_login,
        "email_verified": bool(getattr(user, "email_verified", False)),
        "is_organization_email": bool(getattr(user, "is_organization_email", False)),
        "organization_domain": getattr(user, "organization_domain", None),
        "auth_provider": getattr(user, "auth_provider", "github"),
        "is_trusted_publisher": bool(getattr(user, "is_trusted_publisher", False)),
    }

@app.post("/auth/accept-publisher-agreement")
def accept_agreement(user: User = Depends(_require_jwt_user), db: Session = Depends(get_db)):
    if not user.accepted_publisher_agreement_at:
        user.accepted_publisher_agreement_at = datetime.datetime.utcnow()
        db.commit()
        email = _get_user_email(db, user.id)
        if email:
            _send_email(email, "Publisher Agreement Accepted",
                f"<p>Hi {user.display_name}! You can now generate API keys and submit apps. "
                f"Go to <a href='https://admin.agl-store.cyou/developer'>developer dashboard</a>.</p>")
    return {"message": "Publisher agreement accepted", "accepted_at": str(user.accepted_publisher_agreement_at)}

# ── Developer API Keys ─────────────────────────────────────────────────────
@app.post("/developer/keys", status_code=201)
def create_dev_key(
    body: CreateKeyRequest,
    user: User = Depends(_require_jwt_user),
    db: Session = Depends(get_db),
):
    """Generate a personal developer API key. Shown ONCE."""
    raw = _TOKEN_PREFIX + secrets.token_urlsafe(32)
    prefix = raw[:len(_TOKEN_PREFIX) + 6]
    record = DeveloperToken(
        user_id=user.id,
        name=body.name,
        token_hash=_hash_token(raw),
        token_prefix=prefix,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    email = _get_user_email(db, user.id)
    if email:
        _email_key_created(email, body.name, prefix)
    return {"id": record.id, "name": record.name, "token": raw, "prefix": prefix, "created_at": str(record.created_at)}

@app.get("/developer/keys")
def list_dev_keys(user: User = Depends(_require_jwt_user), db: Session = Depends(get_db)):
    keys = db.query(DeveloperToken).filter(DeveloperToken.user_id == user.id).order_by(DeveloperToken.created_at.desc()).all()
    return [{"id": k.id, "name": k.name, "prefix": k.token_prefix, "is_active": k.is_active, "created_at": str(k.created_at), "last_used_at": str(k.last_used_at) if k.last_used_at else None} for k in keys]

@app.delete("/developer/keys/{key_id}", status_code=204)
def revoke_dev_key(key_id: int, user: User = Depends(_require_jwt_user), db: Session = Depends(get_db)):
    record = db.query(DeveloperToken).filter(DeveloperToken.id == key_id, DeveloperToken.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Key not found")
    record.is_active = False
    db.commit()

# ── App Submission ─────────────────────────────────────────────────────────
@app.post("/developer/submit", status_code=201)
def submit_app(
    body: SubmitAppRequest,
    user: User = Depends(_get_dev_user),
    db: Session = Depends(get_db),
):
    """Submit an app for listing on PensHub store."""
    parts = body.app_id.split(".")
    if len(parts) < 3:
        raise HTTPException(status_code=422, detail="app_id must be reverse-domain (e.g. com.example.MyApp)")
    existing = db.query(AppSubmission).filter(
        AppSubmission.app_id == body.app_id,
        AppSubmission.status.in_(["pending", "approved"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Active submission #{existing.id} already exists for {body.app_id}")
    sub = AppSubmission(
        user_id=user.id,
        app_id=body.app_id,
        name=body.name,
        summary=body.summary,
        description=body.description,
        icon=body.icon,
        homepage=body.homepage,
        license=body.license,
        app_type=body.app_type,
        categories=body.categories,
        tags=body.tags,
        screenshots=[s.model_dump() for s in body.screenshots],
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    email = _get_user_email(db, user.id)
    if email:
        _email_submitted(email, body.name, body.app_id, sub.id)
    _email_admin_new_sub(body.name, body.app_id, user.display_name or f"User#{user.id}", sub.id)
    # [HOOK] enqueue scan + notify
    try:
        _enqueue_scan(ScanJob(submission_id=sub.id, app_name=body.name or body.app_id,
            developer_name=user.display_name or f"User#{user.id}"))
        alert_new_submission(sub.id, body.name or body.app_id, user.display_name or f"User#{user.id}")
    except Exception: pass
    return {"id": sub.id, "app_id": sub.app_id, "name": sub.name, "status": sub.status, "submitted_at": str(sub.submitted_at)}

@app.get("/developer/submissions")
def list_my_submissions(user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    subs = db.query(AppSubmission).filter(AppSubmission.user_id == user.id).order_by(AppSubmission.submitted_at.desc()).all()
    return [{"id": s.id, "app_id": s.app_id, "name": s.name, "status": s.status, "submitted_at": str(s.submitted_at), "rejection_reason": s.rejection_reason} for s in subs]

@app.get("/developer/submissions/{sub_id}")
def get_my_submission(sub_id: int, user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    sub = db.query(AppSubmission).filter(AppSubmission.id == sub_id, AppSubmission.user_id == user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"id": sub.id, "app_id": sub.app_id, "name": sub.name, "summary": sub.summary, "description": sub.description, "icon": sub.icon, "homepage": sub.homepage, "license": sub.license, "app_type": sub.app_type, "categories": sub.categories, "tags": sub.tags or [], "screenshots": sub.screenshots, "status": sub.status, "rejection_reason": sub.rejection_reason, "submitted_at": str(sub.submitted_at)}

@app.put("/developer/submissions/{sub_id}")
def update_submission(sub_id: int, body: SubmitAppRequest, user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    sub = db.query(AppSubmission).filter(AppSubmission.id == sub_id, AppSubmission.user_id == user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status == "approved":
        raise HTTPException(status_code=409, detail="Cannot edit an approved submission")
    sub.name = body.name; sub.summary = body.summary; sub.description = body.description
    sub.icon = body.icon; sub.homepage = body.homepage; sub.license = body.license
    sub.app_type = body.app_type; sub.categories = body.categories; sub.tags = body.tags
    sub.screenshots = [s.model_dump() for s in body.screenshots]
    sub.status = "pending"; sub.rejection_reason = None
    sub.submitted_at = datetime.datetime.utcnow(); sub.reviewed_at = None
    db.commit()
    return {"id": sub.id, "app_id": sub.app_id, "name": sub.name, "status": sub.status, "submitted_at": str(sub.submitted_at)}

# ── Admin Review ───────────────────────────────────────────────────────────
@app.get("/admin/submissions")
def list_submissions(
    status: Optional[str] = Query("pending"),
    admin: User = Depends(_require_jwt_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AppSubmission)
    if status:
        q = q.filter(AppSubmission.status == status)
    subs = q.order_by(AppSubmission.submitted_at.asc()).all()
    result = []
    for s in subs:
        dev = db.query(User).filter(User.id == s.user_id).first()
        result.append({"id": s.id, "app_id": s.app_id, "name": s.name, "developer_name": dev.display_name if dev else None, "status": s.status, "submitted_at": str(s.submitted_at)})
    return result

@app.get("/admin/submissions/{sub_id}")
def get_submission(sub_id: int, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    sub = db.query(AppSubmission).filter(AppSubmission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    dev = db.query(User).filter(User.id == sub.user_id).first()
    return {"id": sub.id, "app_id": sub.app_id, "name": sub.name, "summary": sub.summary, "description": sub.description, "icon": sub.icon, "homepage": sub.homepage, "license": sub.license, "app_type": sub.app_type, "categories": sub.categories, "tags": sub.tags or [], "screenshots": sub.screenshots, "status": sub.status, "rejection_reason": sub.rejection_reason, "submitted_at": str(sub.submitted_at), "reviewed_at": str(sub.reviewed_at) if sub.reviewed_at else None, "developer": {"id": dev.id if dev else None, "name": dev.display_name if dev else None, "email": _get_user_email(db, sub.user_id)}}

@app.post("/admin/submissions/{sub_id}/approve")
def approve_submission(sub_id: int, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    sub = db.query(AppSubmission).filter(AppSubmission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status == "approved":
        raise HTTPException(status_code=409, detail="Already approved")
    now = datetime.datetime.utcnow()
    dev = db.query(User).filter(User.id == sub.user_id).first()
    app_rec = db.query(App).filter(App.id == sub.app_id).first()
    if app_rec:
        app_rec.name = sub.name; app_rec.summary = sub.summary; app_rec.description = sub.description
        app_rec.icon = sub.icon; app_rec.developer_name = dev.display_name if dev else None
        app_rec.project_license = sub.license; app_rec.updated_at = now
    else:
        app_rec = App(
            id=sub.app_id, name=sub.name, summary=sub.summary,
            description=sub.description, icon=sub.icon,
            type=sub.app_type or "desktop-application",
            developer_name=dev.display_name if dev else None,
            project_license=sub.license, is_free_license=True,
            added_at=now, updated_at=now,
        )
        db.add(app_rec)
        db.flush()
    if sub.categories:
        app_rec.categories = []
        for cat_name in sub.categories:
            cat = db.query(Category).filter(Category.name == cat_name).first()
            if not cat:
                cat = Category(name=cat_name, description=cat_name)
                db.add(cat)
                db.flush()
            app_rec.categories.append(cat)
    if sub.tags:
        app_rec.tags = sub.tags
    # Generate GPG signing certificate (non-fatal if it fails)
    gpg_fingerprint_val = None
    gpg_uid_val = None
    _is_trusted = dev and getattr(dev, 'is_trusted_publisher', False)
    _gpg_expire_days = None if _is_trusted else 1
    try:
        gpg_fingerprint_val, gpg_pub, gpg_uid_val = _generate_gpg_key(
            sub.app_id, sub.name, dev.display_name if dev else "Developer",
            expire_days=_gpg_expire_days)
        app_rec.gpg_fingerprint = gpg_fingerprint_val
        app_rec.gpg_public_key = gpg_pub
        app_rec.gpg_uid = gpg_uid_val
    except Exception as _gpg_err:
        print(f"GPG keygen warning: {_gpg_err}")
    # Trusted publishers get full 1-year listing; unverified get 1-day trial
    if _is_trusted:
        app_rec.is_verified = True
        app_rec.expires_at = now + datetime.timedelta(days=365)
    else:
        app_rec.expires_at = now + datetime.timedelta(days=1)
    app_rec.published = True
    app_rec.owner_user_id = sub.user_id
    app_rec.reminder_30_sent = False
    app_rec.reminder_7_sent = False
    sub.status = "approved"; sub.reviewed_at = now; sub.reviewer_id = admin.id
    db.commit()
    # [HOOK] notify approved
    try:
        _app_obj = db.query(App).filter(App.id == sub.app_id).first() if sub.app_id else None
        alert_submission_approved(sub.id, sub.name or sub.id, sub.app_id or '')
    except Exception:
        pass
    # [HOOK] repo watcher - detect when app appears in OSTree repo
    try:
        _dev = db.query(User).filter(User.id == sub.user_id).first() if sub.user_id else None
        _watch_app(
            app_id=sub.app_id or str(sub.id),
            user_id=sub.user_id or 0,
            submission_id=sub.id,
            developer_name=(_dev.display_name or '') if _dev else '',
            developer_email=_get_user_email(db, sub.user_id) or '',
        )
    except Exception:
        pass

    email = _get_user_email(db, sub.user_id)
    if email:
        expiry_str = app_rec.expires_at.strftime("%B %d, %Y") if app_rec.expires_at else "1 year"
        _send_email(email, f"Congratulations! {sub.name} is now live on PensHub",
            f"<div style=\"font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px\">"
            f"<h2 style=\"color:#16a34a\">{sub.name} is now live!</h2>"
            f"<p>Your app <strong>{sub.name}</strong> (<code>{sub.app_id}</code>) is published on PensHub.</p>"
            f"<h3>Signing Certificate</h3><ul>"
            f"<li><strong>Fingerprint:</strong> <code>{gpg_fingerprint_val or 'pending'}</code></li>"
            f"<li><strong>Expires:</strong> {expiry_str}</li></ul>"
            f"<p>Renew at <a href=\"https://admin.agl-store.cyou/developer/portal\">Developer Portal</a>.</p></div>")
    return {"message": f"App '{sub.name}' approved and live", "app_id": sub.app_id}

@app.post("/admin/submissions/{sub_id}/reject")
def reject_submission(sub_id: int, body: RejectRequest, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="Rejection reason required")
    sub = db.query(AppSubmission).filter(AppSubmission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status == "approved":
        raise HTTPException(status_code=409, detail="Cannot reject an approved submission")
    sub.status = "rejected"; sub.rejection_reason = body.reason.strip()
    sub.reviewed_at = datetime.datetime.utcnow(); sub.reviewer_id = admin.id
    db.commit()
    # [HOOK] notify rejected
    try:
        _reason = getattr(body, 'reason', '') or ''
        alert_submission_rejected(sub.id, sub.name or sub.id, _reason)
    except Exception:
        pass

    email = _get_user_email(db, sub.user_id)
    if email:
        _email_rejected(email, sub.name, sub.app_id, body.reason)
    return {"message": f"Submission #{sub_id} rejected"}


# ── GitHub OAuth2 ──────────────────────────────────────────────────────────────
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_OAUTH_SCOPES = "read:user,user:email"
FRONTEND_ADMIN_URL = os.getenv("FRONTEND_ADMIN_URL", "https://admin.agl-store.cyou")

@app.get("/auth/github/authorize")
def github_authorize():
    """Redirect the browser to GitHub's OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured — set GITHUB_CLIENT_ID")
    state = secrets.token_urlsafe(16)
    callback_url = f"{FLAT_MANAGER_URL.replace('hub.', 'admin.')}/api/auth/github/callback"
    # Use admin domain as callback base (proxied through admin.agl-store.cyou/api/*)
    callback_url = f"{FRONTEND_ADMIN_URL}/api/auth/github/callback"
    params = urllib.parse.urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": callback_url,
        "scope": GITHUB_OAUTH_SCOPES,
        "state": state,
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/callback")
def github_callback(code: str, state: str = "", db: Session = Depends(get_db)):
    """GitHub redirects here with ?code=. Exchange for token, log user in."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    # Exchange code for access token
    token_req = urllib.request.Request(
        "https://github.com/login/oauth/access_token",
        data=urllib.parse.urlencode({
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        }).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_data = _json.loads(resp.read())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub token exchange failed: {e}")

    gh_token = token_data.get("access_token")
    if not gh_token:
        error = token_data.get("error_description", token_data.get("error", "No token returned"))
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")

    # Get GitHub user info
    user_req = urllib.request.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            gh_user = _json.loads(resp.read())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub user fetch failed: {e}")

    gh_id = str(gh_user.get("id", ""))
    gh_login = gh_user.get("login", "")
    gh_name = gh_user.get("name") or gh_login
    gh_email = gh_user.get("email")
    gh_avatar = gh_user.get("avatar_url", "")

    # If no public email, fetch primary verified email
    if not gh_email:
        try:
            email_req = urllib.request.Request(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(email_req, timeout=10) as resp:
                emails = _json.loads(resp.read())
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    gh_email = e.get("email")
                    break
        except Exception:
            pass

    now = datetime.datetime.utcnow()

    # Find existing connected account
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.provider == "github",
        ConnectedAccount.provider_user_id == int(gh_id),
    ).first()

    if not account:
        # Admin OAuth: no auto-signup — GitHub account must be pre-linked to an admin user
        error_msg = urllib.parse.quote("No admin account is linked to this GitHub profile. Ask your system administrator to link your GitHub account first.")
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error={error_msg}", status_code=302)

    user = account.user

    # Only admin and reviewer roles may access the admin panel via GitHub OAuth
    user_role = getattr(user, "role", "developer")
    if user_role not in ("admin", "reviewer"):
        error_msg = urllib.parse.quote(f"Your account ({gh_login}) has role '{user_role}' and cannot access the admin panel.")
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error={error_msg}", status_code=302)

    # Update linked account metadata
    account.login = gh_login
    account.avatar_url = gh_avatar
    account.display_name = gh_name
    account.email = gh_email
    account.last_used = now

    db.commit()
    db.refresh(user)

    jwt_token = _make_jwt(user.id, getattr(user, "role", "developer"))

    # Redirect to frontend with token in URL fragment (not query string — won't be logged)
    from fastapi.responses import RedirectResponse
    frontend_url = f"{FRONTEND_ADMIN_URL}/#github_token={jwt_token}"
    return RedirectResponse(frontend_url, status_code=302)



@app.get("/auth/github/link")
def github_link_start(admin: User = Depends(_require_jwt_admin)):
    """Start GitHub OAuth flow to link a GitHub account to the current admin user."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    state = secrets.token_urlsafe(16)
    callback_url = f"{FRONTEND_ADMIN_URL}/api/auth/github/link-callback"
    params = urllib.parse.urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": callback_url,
        "scope": GITHUB_OAUTH_SCOPES,
        "state": state,
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/link-callback")
def github_link_callback(code: str, state: str = "", token: str = Query(None), db: Session = Depends(get_db)):
    """GitHub redirects here after linking. token= is the admin JWT passed as query param."""
    import json as _json
    # Validate the admin JWT from query param (passed by frontend)
    if not token:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=missing_token", status_code=302)
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["sub"]
        role = payload.get("role", "developer")
    except Exception:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=invalid_token", status_code=302)
    if role not in ("admin", "reviewer"):
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=not_admin", status_code=302)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=user_not_found", status_code=302)

    # Exchange code for token
    token_req = urllib.request.Request(
        "https://github.com/login/oauth/access_token",
        data=urllib.parse.urlencode({
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        }).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_data = _json.loads(resp.read())
    except Exception as ex:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=github_exchange_failed", status_code=302)

    gh_token = token_data.get("access_token")
    if not gh_token:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=no_github_token", status_code=302)

    # Get GitHub user info
    user_req = urllib.request.Request(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            gh_user = _json.loads(resp.read())
    except Exception:
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error=github_user_failed", status_code=302)

    gh_id = int(gh_user.get("id", 0))
    gh_login = gh_user.get("login", "")
    gh_name = gh_user.get("name") or gh_login
    gh_email = gh_user.get("email", "")
    gh_avatar = gh_user.get("avatar_url", "")
    now = datetime.datetime.utcnow()

    # Check if this GitHub account is already linked to a different user
    existing = db.query(ConnectedAccount).filter(
        ConnectedAccount.provider == "github",
        ConnectedAccount.provider_user_id == gh_id,
    ).first()
    if existing and existing.user_id != user_id:
        error_msg = urllib.parse.quote(f"GitHub account @{gh_login} is already linked to a different user.")
        return RedirectResponse(f"{FRONTEND_ADMIN_URL}/#error={error_msg}", status_code=302)

    if existing:
        existing.login = gh_login
        existing.avatar_url = gh_avatar
        existing.display_name = gh_name
        existing.email = gh_email
        existing.last_used = now
    else:
        account = ConnectedAccount(
            user_id=user_id,
            provider="github",
            provider_user_id=gh_id,
            login=gh_login,
            avatar_url=gh_avatar,
            display_name=gh_name,
            email=gh_email,
            last_used=now,
            created_at=now,
        )
        db.add(account)

    db.commit()
    success_msg = urllib.parse.quote(f"GitHub account @{gh_login} linked successfully.")
    return RedirectResponse(f"{FRONTEND_ADMIN_URL}/admin/settings#github_linked={success_msg}", status_code=302)

@app.get("/admin/stats")
def admin_stats(admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    return {
        "apps_live": db.query(App).count(),
        "submissions": {
            "pending": db.query(AppSubmission).filter(AppSubmission.status == "pending").count(),
            "approved": db.query(AppSubmission).filter(AppSubmission.status == "approved").count(),
            "rejected": db.query(AppSubmission).filter(AppSubmission.status == "rejected").count(),
        },
        "active_developer_tokens": db.query(DeveloperToken).filter(DeveloperToken.is_active == True).count(),
        "trusted_publishers": db.query(User).filter(User.is_trusted_publisher == True).count(),
        "verified_apps": db.query(App).filter(App.is_verified == True, App.published == True).count(),
    }

@app.get("/admin/users")
def list_users(admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    users = db.query(User).limit(100).all()
    return [{"id": u.id, "display_name": u.display_name, "role": getattr(u, "role", "user"), "accepted_publisher_agreement": bool(u.accepted_publisher_agreement_at), "is_trusted_publisher": bool(u.is_trusted_publisher), "trusted_at": str(u.trusted_at) if u.trusted_at else None, "app_count": db.query(App).filter(App.owner_user_id == u.id).count(), "email": getattr(u, "email", None), "email_verified": bool(getattr(u, "email_verified", False)), "is_organization_email": bool(getattr(u, "is_organization_email", False)), "organization_domain": getattr(u, "organization_domain", None), "auth_provider": getattr(u, "auth_provider", "github")} for u in users]

@app.put("/admin/users/{user_id}/role")
def set_user_role(user_id: int, role: str = Query(...), admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    if role not in ("user", "publisher", "reviewer", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"message": f"User {user_id} role set to {role}"}


# ── Developer: My Apps + Renewal ──────────────────────────────────────────
@app.get("/developer/my-apps")
def list_my_apps(user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    """List apps owned by this developer with expiry info."""
    apps_list = db.query(App).filter(App.owner_user_id == user.id).all()
    now = datetime.datetime.utcnow()
    result = []
    for a in apps_list:
        days_left = (a.expires_at - now).days if a.expires_at else None
        result.append({"id": a.id, "name": a.name, "published": a.published,
            "expires_at": str(a.expires_at) if a.expires_at else None,
            "days_until_expiry": days_left, "gpg_fingerprint": a.gpg_fingerprint,
            "gpg_uid": a.gpg_uid, "gpg_public_key": a.gpg_public_key,
            "updated_at": str(a.updated_at)})
    return result

@app.post("/developer/my-apps/{app_id}/renew")
def renew_app(app_id: str, user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    """Renew app — generates a new GPG key and extends expiry by 1 year."""
    app_rec = db.query(App).filter(App.id == app_id, App.owner_user_id == user.id).first()
    if not app_rec:
        raise HTTPException(status_code=404, detail="App not found or not owned by you")
    now = datetime.datetime.utcnow()
    try:
        fp, pub, uid = _generate_gpg_key(app_id, app_rec.name or app_id, user.display_name or "Developer")
        app_rec.gpg_fingerprint = fp
        app_rec.gpg_public_key = pub
        app_rec.gpg_uid = uid
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPG key generation failed: {e}")
    app_rec.expires_at = now + datetime.timedelta(days=365)
    app_rec.published = True
    app_rec.reminder_30_sent = False
    app_rec.reminder_7_sent = False
    app_rec.updated_at = now
    db.commit()
    new_expiry = app_rec.expires_at.strftime("%B %d, %Y")
    email = _get_user_email(db, user.id)
    if email:
        _email_app_renewed(email, app_rec.name or app_id, app_id, new_expiry)
    return {"message": "App renewed successfully", "app_id": app_id,
            "expires_at": str(app_rec.expires_at), "gpg_fingerprint": app_rec.gpg_fingerprint,
            "gpg_uid": app_rec.gpg_uid}

# ── Admin: App Lifecycle Management ───────────────────────────────────────
@app.get("/admin/apps")
def admin_list_all_apps(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0),
    admin: User = Depends(_require_jwt_admin),
    db: Session = Depends(get_db),
):
    """Admin: list ALL apps including unpublished and expired."""
    _now = datetime.datetime.utcnow()
    q = db.query(App)
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(App.name.ilike(like) | App.developer_name.ilike(like) | App.id.ilike(like))
    if status == "published":
        q = q.filter(App.published == True).filter((App.expires_at == None) | (App.expires_at > _now))
    elif status == "unpublished":
        q = q.filter(App.published == False)
    elif status == "expired":
        q = q.filter(App.expires_at != None).filter(App.expires_at <= _now)
    elif status == "expiring":
        soon = _now + datetime.timedelta(days=30)
        q = q.filter(App.published == True).filter(App.expires_at != None).filter(App.expires_at > _now).filter(App.expires_at <= soon)
    return [
        {
            "id": a.id, "name": a.name, "summary": a.summary,
            "developer_name": a.developer_name, "icon": a.icon, "type": a.type,
            "published": a.published, "is_verified": bool(a.is_verified),
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "added_at": a.added_at.isoformat() if a.added_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "owner_user_id": a.owner_user_id,
            "gpg_fingerprint": a.gpg_fingerprint,
            "categories": [cat.name for cat in a.categories],
        }
        for a in q.order_by(App.updated_at.desc()).offset(offset).limit(limit).all()
    ]

@app.post("/admin/apps/{app_id}/unpublish")
def admin_unpublish_app(app_id: str, body: UnpublishRequest,
    admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    app_rec = db.query(App).filter(App.id == app_id).first()
    if not app_rec:
        raise HTTPException(status_code=404, detail="App not found")
    app_rec.published = False
    app_rec.updated_at = datetime.datetime.utcnow()
    db.commit()
    if app_rec.owner_user_id:
        email = _get_user_email(db, app_rec.owner_user_id)
        if email:
            _email_app_unpublished_admin(email, app_rec.name or app_id, app_id, body.reason)
    return {"message": f"App {app_id} unpublished"}

@app.post("/admin/apps/{app_id}/publish")
def admin_publish_app(app_id: str, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    app_rec = db.query(App).filter(App.id == app_id).first()
    if not app_rec:
        raise HTTPException(status_code=404, detail="App not found")
    app_rec.published = True
    app_rec.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"message": f"App {app_id} published"}

@app.post("/admin/apps/{app_id}/extend")
def admin_extend_app(app_id: str, body: ExtendRequest,
    admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    """Extend app expiry by N days (default 365)."""
    app_rec = db.query(App).filter(App.id == app_id).first()
    if not app_rec:
        raise HTTPException(status_code=404, detail="App not found")
    now = datetime.datetime.utcnow()
    base = max(app_rec.expires_at or now, now)
    app_rec.expires_at = base + datetime.timedelta(days=body.days)
    app_rec.reminder_30_sent = False
    app_rec.reminder_7_sent = False
    app_rec.updated_at = now
    db.commit()
    return {"message": f"App {app_id} extended", "new_expires_at": str(app_rec.expires_at)}

# ── Internal: Expiry Checker (called by cron) ─────────────────────────────
@app.post("/internal/check-expiry")
def check_expiry(_: bool = Depends(require_admin_key), db: Session = Depends(get_db)):
    """Cron endpoint: unpublish expired apps, send 30/7 day reminders."""
    now = datetime.datetime.utcnow()
    unpublished, reminded_30, reminded_7 = [], [], []
    live_apps = db.query(App).filter(App.published == True, App.expires_at != None).all()
    for a in live_apps:
        days_left = (a.expires_at - now).days
        email = _get_user_email(db, a.owner_user_id) if a.owner_user_id else None
        if days_left < 0:
            a.published = False
            a.updated_at = now
            unpublished.append(a.id)
            if email:
                _email_app_expired(email, a.name or a.id, a.id)
                try: alert_app_expired(a.name or a.id, a.id)
                except Exception: pass
        elif days_left <= 7 and not a.reminder_7_sent:
            a.reminder_7_sent = True
            reminded_7.append(a.id)
            if email:
                _email_expiry_reminder(email, a.name or a.id, a.id, days_left)
                try: alert_app_expiring(a.name or a.id, a.id, days_left)
                except Exception: pass
        elif days_left <= 30 and not a.reminder_30_sent:
            a.reminder_30_sent = True
            reminded_30.append(a.id)
            if email:
                _email_expiry_reminder(email, a.name or a.id, a.id, days_left)
    db.commit()
    # Also check publisher personal GPG keys
    expired_pub_keys = db.query(DeveloperGpgKey).filter(
        DeveloperGpgKey.is_active == True,
        DeveloperGpgKey.expires_at != None,
        DeveloperGpgKey.expires_at < now
    ).all()
    for k in expired_pub_keys:
        k.is_active = False
        owner = db.query(User).filter(User.id == k.user_id).first()
        if owner:
            # Remove verified badge from their apps
            db.query(App).filter(App.owner_user_id == k.user_id).update({"is_verified": False})
            email = _get_user_email(db, k.user_id)
            if email:
                _email_publisher_key_expired(email, owner.display_name or f"user{k.user_id}")
    db.commit()
    return {"checked": len(live_apps), "unpublished": unpublished,
            "reminded_30_days": reminded_30, "reminded_7_days": reminded_7,
            "publisher_keys_expired": [k.user_id for k in expired_pub_keys]}


# ── Trusted Publisher Management ──────────────────────────────────────────
@app.post("/admin/users/{user_id}/trust")
def trust_publisher(user_id: int, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    """Mark a developer as a Trusted Publisher and generate their personal GPG key."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.datetime.utcnow()
    # Generate personal publisher GPG key
    dev_name = user.display_name or f"user{user_id}"
    email_addr = _get_user_email(db, user_id) or f"dev{user_id}@agl-store.cyou"
    fingerprint, public_key, uid = None, None, None
    try:
        fingerprint, public_key, uid = _generate_gpg_key(
            f"publisher-{user_id}", dev_name, dev_name)
        # Deactivate old keys
        db.query(DeveloperGpgKey).filter(DeveloperGpgKey.user_id == user_id).update({"is_active": False})
        gpg_key = DeveloperGpgKey(
            user_id=user_id,
            fingerprint=fingerprint,
            public_key=public_key,
            uid=uid,
            created_at=now,
            expires_at=now + datetime.timedelta(days=365),
            is_active=True,
        )
        db.add(gpg_key)
    except Exception as e:
        print(f"Publisher GPG keygen warning: {e}")
    # Mark trusted
    user.is_trusted_publisher = True
    user.trusted_at = now
    user.trusted_by = admin.id
    # Mark all their existing apps as verified
    db.query(App).filter(App.owner_user_id == user_id, App.published == True).update({"is_verified": True})
    db.commit()
    expires_str = (now + datetime.timedelta(days=365)).strftime("%B %d, %Y")
    if email_addr and email_addr != f"dev{user_id}@agl-store.cyou":
        _email_trusted_publisher(email_addr, dev_name, fingerprint or "N/A", expires_str)
    return {
        "message": f"{dev_name} is now a Trusted Publisher",
        "user_id": user_id,
        "gpg_fingerprint": fingerprint,
        "gpg_uid": uid,
        "key_expires": expires_str,
    }

@app.post("/admin/users/{user_id}/untrust")
def untrust_publisher(user_id: int, admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    """Revoke trusted publisher status. Apps lose Verified badge."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_trusted_publisher = False
    # Deactivate personal GPG keys
    db.query(DeveloperGpgKey).filter(DeveloperGpgKey.user_id == user_id).update({"is_active": False})
    # Remove verified badge from their apps
    db.query(App).filter(App.owner_user_id == user_id).update({"is_verified": False})
    db.commit()
    return {"message": f"Trusted publisher status revoked for user {user_id}"}

# ── Developer: Personal GPG Key ────────────────────────────────────────────
@app.get("/developer/my-gpg-key")
def get_my_gpg_key(user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    """Get the developer's active personal signing key."""
    key = db.query(DeveloperGpgKey).filter(
        DeveloperGpgKey.user_id == user.id,
        DeveloperGpgKey.is_active == True
    ).order_by(DeveloperGpgKey.created_at.desc()).first()
    if not key:
        return {"has_key": False, "is_trusted_publisher": bool(user.is_trusted_publisher)}
    now = datetime.datetime.utcnow()
    days_left = (key.expires_at - now).days if key.expires_at else None
    return {
        "has_key": True,
        "is_trusted_publisher": bool(user.is_trusted_publisher),
        "fingerprint": key.fingerprint,
        "uid": key.uid,
        "public_key": key.public_key,
        "created_at": str(key.created_at),
        "expires_at": str(key.expires_at) if key.expires_at else None,
        "days_until_expiry": days_left,
        "is_active": key.is_active,
    }

@app.post("/developer/my-gpg-key/renew")
def renew_my_gpg_key(user: User = Depends(_get_dev_user), db: Session = Depends(get_db)):
    """Renew personal publisher signing key (only for trusted publishers)."""
    if not getattr(user, "is_trusted_publisher", False):
        raise HTTPException(status_code=403, detail="Only trusted publishers can renew their signing key")
    now = datetime.datetime.utcnow()
    dev_name = user.display_name or f"user{user.id}"
    try:
        fingerprint, public_key, uid = _generate_gpg_key(
            f"publisher-{user.id}", dev_name, dev_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPG key generation failed: {e}")
    # Deactivate old keys
    db.query(DeveloperGpgKey).filter(DeveloperGpgKey.user_id == user.id).update({"is_active": False})
    new_key = DeveloperGpgKey(
        user_id=user.id,
        fingerprint=fingerprint,
        public_key=public_key,
        uid=uid,
        created_at=now,
        expires_at=now + datetime.timedelta(days=365),
        is_active=True,
    )
    db.add(new_key)
    # Re-verify all their published apps
    db.query(App).filter(App.owner_user_id == user.id, App.published == True).update({"is_verified": True})
    db.commit()
    return {
        "message": "Publisher signing key renewed",
        "fingerprint": fingerprint,
        "uid": uid,
        "expires_at": str(now + datetime.timedelta(days=365)),
    }

# ── Legacy flat-manager token endpoint (kept for backward compat) ──────────
@app.post("/developer/token")
def issue_flat_manager_token(req: IssueTokenRequest, _: bool = Depends(require_admin_key)):
    if req.role not in ("developer", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'developer' or 'admin'")
    if req.role == "developer" and not req.app_id:
        raise HTTPException(status_code=400, detail="app_id required for developer role")
    cmd = [GENTOKEN_BIN, "--secret", FLAT_MANAGER_SECRET, "--name", req.developer_name, "--repo", "stable", "--scope", "build", "--scope", "upload"]
    if req.role == "admin":
        cmd += ["--scope", "publish", "--prefix", "*"]
    else:
        cmd += ["--prefix", req.app_id]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"gentoken failed: {result.stderr}")
        token = result.stdout.strip()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="gentoken binary not found")
    app_id_for_script = req.app_id or "com.example.YourApp"
    manifest_name = f"{app_id_for_script}.yml"

    trial_notice = (
        "\n"
        "# ⚠️  TRIAL PUBLISHING — 24-HOUR WINDOW\n"
        "# Your GPG signing key expires in 24 hours.\n"
        "# To get a permanent key and Verified badge, complete identity\n"
        "# verification at https://admin.agl-store.cyou/developer/portal\n"
        "\n"
    ) if req.is_trial else ""

    build_script = (
        "#!/bin/bash\n"
        "# AGL App Store - Build & Publish Script\n"
        f"# Developer: {req.developer_name}\n"
        f"# App ID   : {app_id_for_script}\n"
        f"{trial_notice}"
        "#\n"
        "set -euo pipefail\n\n"
        f'APP_ID="{app_id_for_script}"\n'
        f'MANIFEST="{manifest_name}"\n'
        'BUILD_DIR="flatpak_build"\n'
        'REPO_DIR="repo"\n'
        f'FLAT_MANAGER_URL="{FLAT_MANAGER_URL}"\n'
        f'FLAT_MANAGER_TOKEN="{token}"\n\n'
        'echo "[1/5] Checking prerequisites..."\n'
        'for cmd in flatpak flatpak-builder flat-manager-client curl python3; do\n'
        '    if ! command -v "$cmd" &>/dev/null; then\n'
        '        echo "ERROR: $cmd not found."\n'
        '        echo "  Ubuntu/Debian: sudo apt install flatpak flatpak-builder"\n'
        '        echo "  flat-manager-client: pip install flat-manager-client"\n'
        '        exit 1\n'
        '    fi\n'
        'done\n\n'
        'echo "[2/5] Building Flatpak..."\n'
        'flatpak-builder --force-clean --repo="$REPO_DIR" "$BUILD_DIR" "$MANIFEST"\n\n'
        'echo "[3/5] Creating build slot on AGL hub..."\n'
        'BUILD_ID=$(curl -sf -X POST "$FLAT_MANAGER_URL/api/v1/build" \\\n'
        '    -H "Authorization: Bearer $FLAT_MANAGER_TOKEN" \\\n'
        '    -H "Content-Type: application/json" \\\n'
        "    -d '{\"repo\":\"stable\"}' | python3 -c \"import sys,json; print(json.load(sys.stdin)['id'])\")\n"
        'echo "  Build ID: $BUILD_ID"\n\n'
        'echo "[4/5] Uploading build..."\n'
        'flat-manager-client push \\\n'
        '    --token "$FLAT_MANAGER_TOKEN" \\\n'
        '    "$FLAT_MANAGER_URL" "$BUILD_ID" "./$REPO_DIR"\n\n'
        'echo "[5/5] Committing (triggers AGL review pipeline)..."\n'
        'curl -sf -X POST "$FLAT_MANAGER_URL/api/v1/build/$BUILD_ID/commit" \\\n'
        '    -H "Authorization: Bearer $FLAT_MANAGER_TOKEN"\n'
        'echo ""\n'
        'echo "Done! Your app will appear at https://agl-store.cyou after review."\n'
    )

    # Generate trial GPG key (1-day) for unverified developers
    trial_gpg = None
    if req.is_trial and req.app_id:
        try:
            _fp, _pub, _uid = _generate_gpg_key(
                req.app_id, req.app_id.split(".")[-1], req.developer_name,
                expire_days=1)
            trial_gpg = {"fingerprint": _fp, "public_key": _pub, "uid": _uid}
        except Exception as _e:
            trial_gpg = {"error": str(_e)}

    # Flutter Flatpak manifest
    flutter_manifest = (
        f"# Flutter Flatpak manifest for {app_id_for_script}\n"
        "# Prerequisites: flatpak-builder, flutter SDK, org.freedesktop.Platform//23.08\n"
        "# Install runtime: flatpak install flathub org.freedesktop.Platform//23.08 org.freedesktop.Sdk//23.08\n\n"
        f"app-id: {app_id_for_script}\n"
        "runtime: org.freedesktop.Platform\n"
        "runtime-version: '23.08'\n"
        "sdk: org.freedesktop.Sdk\n"
        f"command: {app_id_for_script.split('.')[-1].lower()}\n\n"
        "finish-args:\n"
        "  - --socket=wayland\n"
        "  - --socket=fallback-x11\n"
        "  - --socket=pulseaudio\n"
        "  - --share=network\n"
        "  - --share=ipc\n"
        "  - --device=dri\n\n"
        "modules:\n"
        "  - name: flutter-app\n"
        "    buildsystem: simple\n"
        "    sources:\n"
        "      - type: git\n"
        "        url: .\n"
        "        branch: main\n"
        "    build-commands:\n"
        "      - flutter build linux --release\n"
        f"      - cp -r build/linux/x64/release/bundle /app/lib/{app_id_for_script}\n"
        f"      - install -Dm755 /dev/stdin /app/bin/{app_id_for_script.split('.')[-1].lower()} <<'EOF'\n"
        "#!/bin/sh\n"
        f"exec /app/lib/{app_id_for_script}/$(basename $(ls /app/lib/{app_id_for_script}/*.so | head -1 | sed 's/.so//')) \"$@\"\n"
        "EOF\n"
    )

    sample_manifest = (
        f"# Example Flatpak manifest — rename to {manifest_name}\n"
        "# Reference: https://docs.flatpak.org/en/latest/manifests.html\n"
        "# For Flutter apps, use the flutter_manifest field instead.\n\n"
        f"app-id: {app_id_for_script}\n"
        "runtime: org.gnome.Platform\n"
        "runtime-version: '45'\n"
        "sdk: org.gnome.Sdk\n"
        "command: app.py\n\n"
        "finish-args:\n"
        "  - --socket=wayland\n"
        "  - --socket=fallback-x11\n"
        "  - --socket=pulseaudio\n"
        "  - --share=network\n\n"
        "modules:\n"
        f"  - name: {app_id_for_script.split('.')[-1].lower()}\n"
        "    buildsystem: simple\n"
        "    sources:\n"
        "      - type: file\n"
        "        path: app.py\n"
        "    build-commands:\n"
        "      - install -D app.py /app/bin/app.py\n"
        "      - chmod +x /app/bin/app.py\n"
    )

    resp = {
        "token": token,
        "developer_name": req.developer_name,
        "role": req.role,
        "flat_manager_url": FLAT_MANAGER_URL,
        "app_id": req.app_id,
        "is_trial": req.is_trial,
        "build_script": build_script,
        "sample_manifest": sample_manifest,
        "flutter_manifest": flutter_manifest,
        "instructions": (
            f"1. Save build_script as publish.sh and chmod +x publish.sh\n"
            f"2. Save sample_manifest as {manifest_name} (edit to match your app)\n"
            f"   For Flutter: use flutter_manifest instead\n"
            f"3. Run: ./publish.sh\n"
            f"4. Your app will be reviewed and published to agl-store.cyou"
        ),
    }
    if trial_gpg:
        resp["trial_gpg"] = trial_gpg
        resp["trial_expires_in"] = "24 hours"
    return resp

@app.post("/developer/register-app")
def register_app(req: RegisterAppRequest, db: Session = Depends(get_db)):
    existing = db.query(App).filter(App.id == req.app_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="App ID already registered")
    new_app = App(id=req.app_id, name=req.app_id.split(".")[-1], developer_name=req.developer_name, type="desktop-application", added_at=datetime.datetime.utcnow(), updated_at=datetime.datetime.utcnow())
    db.add(new_app)
    db.commit()
    return {"status": "registered", "app_id": req.app_id}

@app.get("/developer/apps")
def list_developer_apps(developer: str = Query(...), db: Session = Depends(get_db)):
    apps_list = db.query(App).filter(App.developer_name.ilike(f"%{developer}%")).all()
    return [{"id": a.id, "name": a.name, "type": a.type, "updated_at": a.updated_at} for a in apps_list]

@app.get("/admin/pending-apps")
def list_pending_apps(admin: User = Depends(_require_jwt_admin), db: Session = Depends(get_db)):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    apps_list = db.query(App).filter(App.added_at >= cutoff).order_by(App.added_at.desc()).limit(50).all()
    return [{"id": a.id, "name": a.name, "developer_name": a.developer_name, "type": a.type, "added_at": a.added_at} for a in apps_list]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("REST_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

# ── Flatpak Security Scanner ──────────────────────────────────────────────────

class ScanRequest(BaseModel):
    manifest_content: Optional[str] = None
    submission_id: Optional[int] = None


@app.get("/admin/repo-watches")
def list_repo_watches(_: bool = Depends(require_admin_key)):
    from repo_watcher import list_watches
    return {"watches": list_watches()}

@app.delete("/admin/repo-watches/{app_id}", status_code=204)
def cancel_repo_watch(app_id: str, _: bool = Depends(require_admin_key)):
    from repo_watcher import cancel_watch
    cancel_watch(app_id)
    return

@app.post("/admin/scan/manifest")
def scan_manifest_endpoint(
    body: ScanRequest,
    admin: User = Depends(_require_jwt_admin),
    db: Session = Depends(get_db),
):
    """Run static analysis on a Flatpak manifest string."""
    if not body.manifest_content:
        raise HTTPException(status_code=400, detail="manifest_content required")
    import json as _json
    result = _scan_flatpak(
        submission_id=body.submission_id or 0,
        manifest_content=body.manifest_content,
    )
    # If submission_id given, store result on the App record
    if body.submission_id:
        sub = db.query(Submission).filter(Submission.id == body.submission_id).first()
        if sub and sub.app_id:
            app_obj = db.query(App).filter(App.id == sub.app_id).first()
            if app_obj:
                import datetime
                app_obj.scan_result = _asdict(result)
                app_obj.scan_verdict = result.verdict
                app_obj.scan_at = datetime.datetime.utcnow()
                db.commit()
    return _asdict(result)


@app.post("/admin/scan/submission/{submission_id}")
def scan_submission_endpoint(
    submission_id: int,
    admin: User = Depends(_require_jwt_admin),
    db: Session = Depends(get_db),
):
    """Trigger a full scan for an existing submission (uses stored manifest)."""
    import datetime as _dt
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    # Get manifest from submission metadata if available
    manifest_content = None
    if sub.metadata_json:
        try:
            meta = sub.metadata_json if isinstance(sub.metadata_json, dict) else __import__("json").loads(sub.metadata_json)
            manifest_content = meta.get("flatpak_manifest")
        except Exception:
            pass
    result = _scan_flatpak(
        submission_id=submission_id,
        manifest_content=manifest_content,
    )
    # Store on app
    if sub.app_id:
        app_obj = db.query(App).filter(App.id == sub.app_id).first()
        if app_obj:
            app_obj.scan_result = _asdict(result)
            app_obj.scan_verdict = result.verdict
            app_obj.scan_at = _dt.datetime.utcnow()
            db.commit()
    return _asdict(result)


@app.get("/admin/scan/submission/{submission_id}/result")
def get_scan_result(
    submission_id: int,
    admin: User = Depends(_require_jwt_admin),
    db: Session = Depends(get_db),
):
    """Get the last scan result for a submission."""
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.app_id:
        app_obj = db.query(App).filter(App.id == sub.app_id).first()
        if app_obj and app_obj.scan_result:
            return app_obj.scan_result
    return {"verdict": "NOT_SCANNED", "findings": [], "risk_score": 0, "summary": "Not yet scanned"}


@app.post("/developer/submissions/{submission_id}/scan")
def developer_submit_manifest(
    submission_id: int,
    body: ScanRequest,
    user: User = Depends(_get_dev_user),
    db: Session = Depends(get_db),
):
    """Developer uploads manifest for pre-submission scanning."""
    sub = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.developer_user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not body.manifest_content:
        raise HTTPException(status_code=400, detail="manifest_content required")
    result = _scan_flatpak(
        submission_id=submission_id,
        manifest_content=body.manifest_content,
    )
    # Store manifest on submission metadata
    import json as _json
    meta = {}
    if sub.metadata_json:
        try:
            meta = sub.metadata_json if isinstance(sub.metadata_json, dict) else _json.loads(sub.metadata_json)
        except Exception:
            pass
    meta["flatpak_manifest"] = body.manifest_content
    sub.metadata_json = meta
    # Store scan result
    if sub.app_id:
        app_obj = db.query(App).filter(App.id == sub.app_id).first()
        if app_obj:
            import datetime as _dt
            app_obj.scan_result = _asdict(result)
            app_obj.scan_verdict = result.verdict
            app_obj.scan_at = _dt.datetime.utcnow()
    db.commit()
    return _asdict(result)

