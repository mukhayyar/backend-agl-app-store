#!/usr/bin/env python3
"""
AGL App Store - GitHub Webhook Auto-Deploy Bot
Listens on :9000 for GitHub push events and redeploys the relevant app.
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
    handlers=[
        logging.FileHandler('/var/log/agl-webhook.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'agl-deploy-secret')

REPO_MAP = {
    'frontend-agl-app-store': {
        'dir': '/root/agl/apps/frontend',
        'build': 'npm install --legacy-peer-deps && npm run build',
        'service': 'agl-frontend',
    },
    'backend-agl-app-store': {
        'dir': '/root/agl',
        'build': None,
        'service': 'agl-rest',
        'extra_services': ['agl-backend'],
    },
    'admin-frontend-agl': {
        'dir': '/root/agl/apps/admin-frontend',
        'build': 'npm install && npm run build',
        'service': 'agl-admin',
    },
    'simple-flatpak-app-collections': {
        'dir': '/root/agl/simple-flatpak-app-collections',
        'build': None,
        'service': None,
    },
}

def verify_signature(payload, signature, secret):
    if not signature:
        return False
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    expected = 'sha256=' + mac.hexdigest()
    return hmac.compare_digest(expected, signature)

def deploy(repo_name):
    config = REPO_MAP.get(repo_name)
    if not config:
        log.warning(f'Unknown repo: {repo_name}')
        return

    d = config['dir']
    log.info(f'Deploying {repo_name} in {d}')

    # Pull latest
    result = subprocess.run(['git', 'pull', '--ff-only'], cwd=d, capture_output=True, text=True)
    log.info(f'git pull: {result.stdout.strip()} {result.stderr.strip()}')

    # Build
    if config['build']:
        result = subprocess.run(config['build'], shell=True, cwd=d, capture_output=True, text=True)
        log.info(f'build: {result.stdout[-500:]} {result.stderr[-200:]}')
        if result.returncode != 0:
            log.error(f'Build failed for {repo_name}')
            return

    # Restart service
    if config.get('service'):
        result = subprocess.run(['systemctl', 'restart', config['service']], capture_output=True, text=True)
        log.info(f'restart {config["service"]}: {result.returncode}')
    for extra in config.get('extra_services', []):
        subprocess.run(['systemctl', 'restart', extra], capture_output=True)
        log.info(f'restart extra service: {extra}')

    log.info(f'Deploy complete: {repo_name}')

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log

    def do_POST(self):
        if self.path not in ('/', '/github-webhook', '/github-webhook/'):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        sig = self.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(body, sig, WEBHOOK_SECRET):
            log.warning('Invalid webhook signature')
            self.send_response(403)
            self.end_headers()
            return

        try:
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        repo = payload.get('repository', {}).get('name', '')
        event = self.headers.get('X-GitHub-Event', '')
        ref = payload.get('ref', '')

        log.info(f'Event: {event}, repo: {repo}, ref: {ref}')

        if event == 'push' and ref in ('refs/heads/main', 'refs/heads/master'):
            deploy(repo)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', 9000))
    log.info(f'AGL webhook bot listening on :{port}')
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    server.serve_forever()

