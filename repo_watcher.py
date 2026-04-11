"""
repo_watcher.py — Background watcher that polls the OSTree/Flatpak repo
for newly published apps and fires events (Telegram alerts + scan).

Usage in rest_api.py:
    from repo_watcher import init_repo_watcher, watch_app

    # At startup
    init_repo_watcher(get_db_factory, App, AppSubmission)

    # After approving a submission
    watch_app(app_id, user_id, submission_id, developer_name)
"""

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)

REPO_PATH = os.getenv("FLATPAK_REPO_PATH", "/srv/flatpak-repo")
POLL_INTERVAL = int(os.getenv("REPO_WATCH_INTERVAL", "60"))   # seconds
WATCH_TIMEOUT_HOURS = int(os.getenv("REPO_WATCH_TIMEOUT_HOURS", "72"))
WATCH_STATE_FILE = os.getenv("REPO_WATCH_STATE", "/root/agl/apps/backend/repo_watch_state.json")

@dataclass
class WatchJob:
    app_id: str
    user_id: int
    submission_id: int
    developer_name: str
    developer_email: str
    enqueued_at: str          # ISO string
    expires_at: str           # ISO string
    detected_at: Optional[str] = None
    notified: bool = False

_jobs: Dict[str, WatchJob] = {}       # keyed by app_id
_lock = threading.Lock()
_started = False
_get_db = None
_App = None
_AppSubmission = None

def _app_in_repo(app_id: str) -> bool:
    """Return True if any ref for app_id exists in the OSTree repo."""
    # Fast path: check filesystem refs directory
    ref_dir = os.path.join(REPO_PATH, "refs", "heads", "app", app_id)
    if os.path.isdir(ref_dir):
        return True
    # Fallback: use ostree CLI
    try:
        result = subprocess.run(
            ["ostree", "refs", f"--repo={REPO_PATH}"],
            capture_output=True, text=True, timeout=10
        )
        prefix = f"app/{app_id}/"
        return any(line.startswith(prefix) or line == f"app/{app_id}" for line in result.stdout.splitlines())
    except Exception as e:
        log.debug("ostree check failed for %s: %s", app_id, e)
    return False

def _get_app_arch_branch(app_id: str) -> Optional[str]:
    """Return 'arch/branch' string for the detected ref, e.g. 'x86_64/master'."""
    ref_dir = os.path.join(REPO_PATH, "refs", "heads", "app", app_id)
    if os.path.isdir(ref_dir):
        for arch in os.listdir(ref_dir):
            arch_dir = os.path.join(ref_dir, arch)
            if os.path.isdir(arch_dir):
                branches = os.listdir(arch_dir)
                if branches:
                    return f"{arch}/{branches[0]}"
    return None

def _save_state():
    try:
        with open(WATCH_STATE_FILE, "w") as f:
            json.dump({app_id: asdict(job) for app_id, job in _jobs.items()}, f, indent=2)
    except Exception as e:
        log.warning("repo_watcher: failed to save state: %s", e)

def _load_state():
    if not os.path.exists(WATCH_STATE_FILE):
        return
    try:
        with open(WATCH_STATE_FILE) as f:
            data = json.load(f)
        now = datetime.utcnow()
        for app_id, job_dict in data.items():
            expires = datetime.fromisoformat(job_dict["expires_at"])
            if expires > now and not job_dict.get("notified"):
                _jobs[app_id] = WatchJob(**job_dict)
        log.info("repo_watcher: resumed %d watch jobs", len(_jobs))
    except Exception as e:
        log.warning("repo_watcher: failed to load state: %s", e)

def _notify(job: WatchJob, arch_branch: str):
    """Fire Telegram alerts and trigger a scan."""
    try:
        from telegram_notifier import _bot_send
        app_id = job.app_id
        name = job.developer_name
        ref = f"app/{app_id}/{arch_branch}"

        # Developer notification
        _bot_send(
            f"✅ <b>Your app is live!</b>\n\n"
            f"<b>{app_id}</b> has been published to the PensHub App Store repo.\n"
            f"Ref: <code>{ref}</code>\n\n"
            f"Users can now install it with:\n"
            f"<pre>flatpak install penshub {app_id}</pre>"
        )

        # Admin notification (developer channel)
        _bot_send(
            f"📦 <b>App Published to Repo</b>\n\n"
            f"App: <code>{app_id}</code>\n"
            f"Developer: {name}\n"
            f"Ref: <code>{ref}</code>\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
    except Exception as e:
        log.warning("repo_watcher: telegram notify failed: %s", e)

    # Trigger scan
    try:
        from scan_queue import ScanJob, enqueue_scan
        enqueue_scan(ScanJob(
            app_id=job.app_id,
            submission_id=job.submission_id,
        ))
    except Exception as e:
        log.debug("repo_watcher: scan enqueue failed (ok if no scan_queue): %s", e)

    # Update DB
    if _get_db and _App:
        try:
            db = next(_get_db())
            app_obj = db.query(_App).filter(_App.id == job.app_id).first()
            if app_obj:
                app_obj.published = True
                db.commit()
            db.close()
        except Exception as e:
            log.warning("repo_watcher: db update failed: %s", e)

# ── Background thread ──────────────────────────────────────────────────────────
def _watcher_loop():
    log.info("repo_watcher: started (poll every %ds, repo=%s)", POLL_INTERVAL, REPO_PATH)
    while True:
        time.sleep(POLL_INTERVAL)
        now = datetime.utcnow()
        with _lock:
            app_ids = list(_jobs.keys())

        for app_id in app_ids:
            with _lock:
                job = _jobs.get(app_id)
                if job is None:
                    continue

            # Expire check
            expires = datetime.fromisoformat(job.expires_at)
            if now > expires:
                log.info("repo_watcher: job expired for %s", app_id)
                with _lock:
                    _jobs.pop(app_id, None)
                    _save_state()
                continue

            # Already notified
            if job.notified:
                with _lock:
                    _jobs.pop(app_id, None)
                continue

            # Poll repo
            if _app_in_repo(app_id):
                arch_branch = _get_app_arch_branch(app_id) or "x86_64/master"
                log.info("repo_watcher: detected %s in repo (%s)", app_id, arch_branch)
                _notify(job, arch_branch)
                with _lock:
                    if app_id in _jobs:
                        _jobs[app_id].detected_at = now.isoformat()
                        _jobs[app_id].notified = True
                        _save_state()
                # Remove after short delay
                threading.Timer(300, lambda a=app_id: _jobs.pop(a, None)).start()
            else:
                log.debug("repo_watcher: %s not yet in repo", app_id)

# ── Public API ─────────────────────────────────────────────────────────────────
def watch_app(
    app_id: str,
    user_id: int,
    submission_id: int,
    developer_name: str = "",
    developer_email: str = "",
):
    """Enqueue an app to be watched for repo publication."""
    now = datetime.utcnow()
    expires = now + timedelta(hours=WATCH_TIMEOUT_HOURS)
    job = WatchJob(
        app_id=app_id,
        user_id=user_id,
        submission_id=submission_id,
        developer_name=developer_name,
        developer_email=developer_email,
        enqueued_at=now.isoformat(),
        expires_at=expires.isoformat(),
    )
    with _lock:
        _jobs[app_id] = job
        _save_state()
    log.info("repo_watcher: watching %s (expires in %dh)", app_id, WATCH_TIMEOUT_HOURS)

def list_watches() -> list:
    """Return all active watch jobs (for admin API)."""
    with _lock:
        return [asdict(j) for j in _jobs.values()]

def cancel_watch(app_id: str) -> bool:
    """Cancel a watch job."""
    with _lock:
        removed = _jobs.pop(app_id, None)
        if removed:
            _save_state()
    return removed is not None

def init_repo_watcher(get_db_factory: Callable, App=None, AppSubmission=None):
    """Call once at FastAPI startup to start the background watcher thread."""
    global _started, _get_db, _App, _AppSubmission
    if _started:
        return
    _started = True
    _get_db = get_db_factory
    _App = App
    _AppSubmission = AppSubmission

    _load_state()
    t = threading.Thread(target=_watcher_loop, daemon=True, name="repo-watcher")
    t.start()
    log.info("repo_watcher: initialized")
