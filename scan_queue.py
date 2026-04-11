"""
AGL App Store — Scan Queue Worker
Background thread that processes Flatpak scan jobs asynchronously.
Submissions are scanned without blocking the API response.
"""
import threading, queue, logging, datetime
import os, sys

log = logging.getLogger(__name__)

# ── Job types ─────────────────────────────────────────────────────────────────

class ScanJob:
    def __init__(self, submission_id: int, app_name: str, developer_name: str,
                 manifest_content: str = None, bundle_path: str = None):
        self.submission_id    = submission_id
        self.app_name         = app_name
        self.developer_name   = developer_name
        self.manifest_content = manifest_content
        self.bundle_path      = bundle_path
        self.queued_at        = datetime.datetime.utcnow()


# ── Worker ────────────────────────────────────────────────────────────────────

class ScanQueueWorker:
    def __init__(self, get_db_session, App, Submission):
        self._q       = queue.Queue(maxsize=100)
        self._App     = App
        self._Sub     = Submission
        self._get_db  = get_db_session
        self._thread  = threading.Thread(target=self._run, daemon=True, name="scan-worker")

    def start(self):
        self._thread.start()
        log.info("Scan queue worker started")

    def enqueue(self, job: ScanJob):
        try:
            self._q.put_nowait(job)
            log.info(f"Queued scan for submission #{job.submission_id} ({job.app_name})")
        except queue.Full:
            log.warning(f"Scan queue full — dropping job for #{job.submission_id}")

    def _run(self):
        while True:
            try:
                job = self._q.get(timeout=5)
                self._process(job)
                self._q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"Scan worker error: {e}", exc_info=True)

    def _process(self, job: ScanJob):
        log.info(f"Processing scan #{job.submission_id}")
        try:
            # Import here to avoid circular issues at module load
            from flatpak_scanner import scan_submission as run_scan, asdict
            from telegram_notifier import alert_scan_result, alert_scan_blocked

            result = run_scan(
                submission_id=job.submission_id,
                manifest_content=job.manifest_content,
                bundle_path=job.bundle_path,
            )
            result_dict = asdict(result)

            # Persist to DB
            db = next(self._get_db())
            try:
                sub = db.query(self._Sub).filter(self._Sub.id == job.submission_id).first()
                if sub and sub.app_id:
                    app_obj = db.query(self._App).filter(self._App.id == sub.app_id).first()
                    if app_obj:
                        app_obj.scan_result  = result_dict
                        app_obj.scan_verdict = result.verdict
                        app_obj.scan_at      = datetime.datetime.utcnow()
                        # Auto-reject BLOCK verdict — move to needs_review flag
                        if result.verdict == "BLOCK":
                            app_obj.scan_blocked = True
                        db.commit()
            finally:
                db.close()

            # Telegram alerts
            if result.verdict == "BLOCK":
                criticals = sum(1 for f in result.findings if f.severity == "CRITICAL")
                alert_scan_blocked(job.submission_id, job.app_name, criticals)
            elif result.verdict == "WARN":
                alert_scan_result(job.submission_id, job.app_name, result_dict)

            log.info(f"Scan #{job.submission_id} done: {result.verdict} ({result.risk_score}/100)")

        except Exception as e:
            log.error(f"Scan failed for #{job.submission_id}: {e}", exc_info=True)


# Singleton — initialized in rest_api.py startup
_worker: ScanQueueWorker = None

def init_worker(get_db_session, App, Submission):
    global _worker
    _worker = ScanQueueWorker(get_db_session, App, Submission)
    _worker.start()
    return _worker

def enqueue_scan(job: ScanJob):
    if _worker is None:
        log.warning("Scan worker not initialized")
        return
    _worker.enqueue(job)
