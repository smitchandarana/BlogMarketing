"""
LinkedIn OAuth 2.0 Authorization Code Flow
-------------------------------------------
Usage (standalone):
    python linkedin_auth.py

From GUI: call run_oauth_flow(on_success, on_error) — runs in a background thread.
"""

import os
import threading
import webbrowser
import urllib.parse
import urllib.request
import json
import secrets
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv, set_key

load_dotenv()

logger = logging.getLogger(__name__)

LINKEDIN_AUTH_URL  = 'https://www.linkedin.com/oauth/v2/authorization'
LINKEDIN_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
REDIRECT_URI       = 'http://localhost:8765/callback'
SCOPES             = 'openid profile w_member_social email'
CALLBACK_PORT      = 8765

_ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')

# ── OAuth state holder ────────────────────────────────────────────────────────
_oauth_state  = {}   # {'state': str, 'server': HTTPServer, 'result': ...}


def _get_credentials():
    client_id     = os.getenv('LINKEDIN_CLIENT_ID', '').strip()
    client_secret = os.getenv('LINKEDIN_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        raise EnvironmentError(
            'LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env'
        )
    return client_id, client_secret


def _build_auth_url(client_id: str, state: str) -> str:
    params = {
        'response_type': 'code',
        'client_id':     client_id,
        'redirect_uri':  REDIRECT_URI,
        'state':         state,
        'scope':         SCOPES,
    }
    return LINKEDIN_AUTH_URL + '?' + urllib.parse.urlencode(params)


def _exchange_code(code: str, client_id: str, client_secret: str) -> str:
    """POST the auth code to LinkedIn and return the access token string."""
    data = urllib.parse.urlencode({
        'grant_type':    'authorization_code',
        'code':          code,
        'redirect_uri':  REDIRECT_URI,
        'client_id':     client_id,
        'client_secret': client_secret,
    }).encode()

    req = urllib.request.Request(
        LINKEDIN_TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode())

    token = body.get('access_token', '')
    if not token:
        raise ValueError('Token exchange failed: ' + json.dumps(body))
    return token


def _save_token(token: str):
    """Write LINKEDIN_ACCESS_TOKEN to .env."""
    set_key(_ENV_PATH, 'LINKEDIN_ACCESS_TOKEN', token)
    os.environ['LINKEDIN_ACCESS_TOKEN'] = token
    logger.info('LinkedIn access token saved to .env')


# ── Local callback HTTP server ────────────────────────────────────────────────

class _CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != '/callback':
            self._respond(404, 'Not Found')
            return

        params = dict(urllib.parse.parse_qsl(parsed.query))
        state  = params.get('state', '')
        code   = params.get('code', '')
        error  = params.get('error', '')

        if error:
            msg = params.get('error_description', error)
            self._respond(400, f'LinkedIn auth error: {msg}')
            _oauth_state['error'] = msg
        elif state != _oauth_state.get('expected_state', ''):
            self._respond(400, 'Invalid state parameter — possible CSRF.')
            _oauth_state['error'] = 'State mismatch'
        elif code:
            self._respond(200,
                '<h2 style="font-family:sans-serif;color:#0B1F3A">'
                'Authorization successful! You can close this tab.</h2>')
            _oauth_state['code'] = code
        else:
            self._respond(400, 'Missing code parameter.')
            _oauth_state['error'] = 'No code received'

        # Signal server to stop after response is sent
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _respond(self, status: int, body: str):
        encoded = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):  # suppress default access log
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def run_oauth_flow(on_success=None, on_error=None):
    """
    Full OAuth flow — blocking until the user authorises (or an error occurs).
    Call from a background thread so the GUI stays responsive.

    on_success(token: str) — called with the new access token
    on_error(msg: str)     — called if anything goes wrong
    """
    _oauth_state.clear()

    try:
        client_id, client_secret = _get_credentials()
    except EnvironmentError as exc:
        if on_error:
            on_error(str(exc))
        return

    state = secrets.token_hex(16)
    _oauth_state['expected_state'] = state

    auth_url = _build_auth_url(client_id, state)

    # Start local callback server
    server = HTTPServer(('127.0.0.1', CALLBACK_PORT), _CallbackHandler)
    _oauth_state['server'] = server

    logger.info('Opening browser for LinkedIn auth: %s', auth_url)
    webbrowser.open(auth_url)

    # serve_forever blocks until _CallbackHandler calls server.shutdown()
    server.serve_forever()
    server.server_close()

    if 'error' in _oauth_state:
        msg = _oauth_state['error']
        if on_error:
            on_error(msg)
        return

    code = _oauth_state.get('code', '')
    if not code:
        if on_error:
            on_error('No authorisation code received.')
        return

    try:
        token = _exchange_code(code, client_id, client_secret)
        _save_token(token)
        if on_success:
            on_success(token)
    except Exception as exc:
        if on_error:
            on_error(str(exc))


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    def _ok(token):
        print('\nAccess token saved:')
        print(token[:40] + '...' if len(token) > 40 else token)

    def _fail(msg):
        print('\nError:', msg)

    print('Starting LinkedIn OAuth flow...')
    print(f'Redirect URI: {REDIRECT_URI}')
    print('Make sure this is registered in your LinkedIn Developer App.\n')
    run_oauth_flow(on_success=_ok, on_error=_fail)
