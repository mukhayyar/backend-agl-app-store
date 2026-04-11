#!/usr/bin/env python3
"""
AGL App Store - GitHub Webhook Auto-Deploy Bot (Docker Compose edition).
Listens on :9000 for GitHub push events and rebuilds/restarts the relevant service.
Requires: Docker socket mounted at /var/run/docker.sock
          Project directory mounted at /workspace
"""
import hmac
import hashlib
import json
import subprocess
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'agl-deploy-secret')
COMPOSE_PROJECT = os.getenv('COMPOSE_PROJECT_NAME', 'agl')
WORKSPACE = os.getenv('WORKSPACE_DIR', '/workspace')

# Map GitHub repo name → docker compose service(s) to rebuild & restart
REPO_MAP = {
    'frontend-agl-app-store': {
        'src': 'apps/frontend',
        'services': ['frontend'],
        'rebuild': True,
    },
    'backend-agl-app-store': {
        'src': 'apps/backend',
        'services': ['backend', 'rest'],
        'rebuild': True,
    },
    'admin-frontend-agl': {
        'src': 'apps/admin-frontend',
        'services': ['admin'],
        'rebuild': True,
    },
}

def compose(args, **kw):
    cmd = ['docker', 'compose', '-p', COMPOSE_PROJECT] + args
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, **kw)

def deploy(repo_name):
    config = REPO_MAP.get(repo_name)
    if not config:
        log.warning(f'Unknown repo: {repo_name}')
        return

    src_dir = os.path.join(WORKSPACE, config['src'])
    log.info(f'Deploying {repo_name} (services: {config["services"]})')

    # Pull latest code
    r = subprocess.run(['git', 'pull', '--ff-only'], cwd=src_dir, capture_output=True, text=True)
    log.info(f'git pull: {r.stdout.strip()} {r.stderr.strip()}')
    if r.returncode != 0:
        log.error('git pull failed - aborting deploy')
        return

    if config.get('rebuild'):
        r = compose(['build', '--no-cache'] + config['services'])
        log.info(f'build: {r.stdout[-800:]} {r.stderr[-200:]}')
        if r.returncode != 0:
            log.error(f'Build failed for {repo_name}')
            return

    r = compose(['up', '-d', '--no-deps'] + config['services'])
    log.info(f'up -d: rc={r.returncode} {r.stderr[-200:]}')
    log.info(f'Deploy complete: {repo_name}')

def verify_signature(payload, signature, secret):
    if not signature:
        return False
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    expected = 'sha256=' + mac.hexdigest()
    return hmac.compare_digest(expected, signature)

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        sig = self.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(body, sig, WEBHOOK_SECRET):
            log.warning('Invalid webhook signature')
            self.send_response(403); self.end_headers(); return
        try:
            payload = json.loads(body)
        except Exception:
            self.send_response(400); self.end_headers(); return
        repo = payload.get('repository', {}).get('name', '')
        event = self.headers.get('X-GitHub-Event', '')
        ref = payload.get('ref', '')
        log.info(f'Event: {event}, repo: {repo}, ref: {ref}')
        if event == 'push' and ref in ('refs/heads/main', 'refs/heads/master'):
            deploy(repo)
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')

if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', 9000))
    log.info(f'AGL webhook bot (Docker mode) listening on :{port}')
    HTTPServer(('0.0.0.0', port), WebhookHandler).serve_forever()
