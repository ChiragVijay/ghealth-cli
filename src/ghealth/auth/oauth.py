import base64
import hashlib
import queue
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from ghealth.config import Config

HTTP_OK = 200


class OAuthRedirectServer(HTTPServer):
    code_queue: queue.Queue[tuple[str | None, str | None]]


class RedirectHandler(BaseHTTPRequestHandler):
    server: OAuthRedirectServer

    def log_message(self, format: str, *args: object) -> None:
        _ = (format, args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if code:
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>G Health CLI Authentication</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        background: #000000;
                        color: #ededed;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                    }
                    .card {
                        background: #0a0a0a;
                        border: 1px solid #333333;
                        border-radius: 8px;
                        padding: 40px 48px;
                        text-align: center;
                        width: 100%;
                        max-width: 360px;
                    }
                    .icon {
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        width: 48px;
                        height: 48px;
                        border-radius: 50%;
                        margin-bottom: 24px;
                    }
                    .icon-success {
                        background: rgba(46, 164, 79, 0.1);
                        color: #2ea44f;
                        border: 1px solid rgba(46, 164, 79, 0.2);
                    }
                    h1 {
                        margin: 0 0 8px;
                        font-size: 20px;
                        font-weight: 600;
                        color: #ffffff;
                        letter-spacing: -0.02em;
                    }
                    p {
                        margin: 0;
                        color: #888888;
                        font-size: 14px;
                        line-height: 1.5;
                    }
                    .sub-text {
                        margin-top: 24px;
                        font-size: 13px;
                        color: #666666;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon icon-success">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    </div>
                    <h1>Authentication Successful</h1>
                    <p>G Health CLI has been successfully authorized.</p>
                    <p class="sub-text">You can safely close this window and return to your terminal.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            self.server.code_queue.put((code, state))
        else:
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>G Health CLI Authentication</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        background: #000000;
                        color: #ededed;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                    }
                    .card {
                        background: #0a0a0a;
                        border: 1px solid #333333;
                        border-radius: 8px;
                        padding: 40px 48px;
                        text-align: center;
                        width: 100%;
                        max-width: 360px;
                    }
                    .icon {
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        width: 48px;
                        height: 48px;
                        border-radius: 50%;
                        margin-bottom: 24px;
                    }
                    .icon-error {
                        background: rgba(248, 81, 73, 0.1);
                        color: #f85149;
                        border: 1px solid rgba(248, 81, 73, 0.2);
                    }
                    h1 {
                        margin: 0 0 8px;
                        font-size: 20px;
                        font-weight: 600;
                        color: #ffffff;
                        letter-spacing: -0.02em;
                    }
                    p {
                        margin: 0;
                        color: #888888;
                        font-size: 14px;
                        line-height: 1.5;
                    }
                    .sub-text {
                        margin-top: 24px;
                        font-size: 13px;
                        color: #666666;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon icon-error">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </div>
                    <h1>Authentication Failed</h1>
                    <p>Could not retrieve authorization code from the redirect URL.</p>
                    <p class="sub-text">Please check terminal output and retry.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            self.server.code_queue.put((None, None))


def generate_pkce() -> tuple[str, str]:
    """Generate a code verifier and code challenge for PKCE."""
    code_verifier = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).decode("utf-8").replace("=", "")
    return code_verifier, code_challenge


def run_local_redirect_server() -> tuple[OAuthRedirectServer, int]:
    """Start a local HTTP server on an ephemeral port to listen for the redirect callback."""
    server = OAuthRedirectServer(("127.0.0.1", 0), RedirectHandler)
    server.code_queue = queue.Queue()
    server.timeout = 1.0
    return server, server.server_address[1]


def extract_code_from_input(user_input: str) -> str:
    """Extract authorization code from either the raw pasted code or redirect URL."""
    user_input = user_input.strip()
    if user_input.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(user_input)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            return code
    return user_input


def exchange_code_for_tokens(
    config: Config,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict:
    """Exchanges an OAuth authorization code for access and refresh tokens."""
    payload = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = httpx.post(config.token_uri, data=payload)
    if resp.status_code != HTTP_OK:
        try:
            err_data = resp.json()
            err_msg = err_data.get("error_description") or err_data.get("error") or resp.text
        except ValueError:
            err_msg = resp.text
        msg = f"Token exchange failed: {err_msg}"
        raise RuntimeError(msg)

    data = resp.json()
    if "expires_in" in data:
        data["expires_at"] = int(time.time()) + data["expires_in"]
    return data


def refresh_access_token(config: Config, refresh_token: str) -> dict:
    """Refresh the access token using the stored refresh token."""
    payload = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = httpx.post(config.token_uri, data=payload)
    if resp.status_code != HTTP_OK:
        try:
            err_data = resp.json()
            err_msg = err_data.get("error_description") or err_data.get("error") or resp.text
        except ValueError:
            err_msg = resp.text
        msg = f"Token refresh failed: {err_msg}"
        raise RuntimeError(msg)

    data = resp.json()
    if "expires_in" in data:
        data["expires_at"] = int(time.time()) + data["expires_in"]
    if "refresh_token" not in data:
        data["refresh_token"] = refresh_token
    return data


def revoke_token(config: Config, token: str) -> None:
    """Revokes the given token (refresh or access token) on Google's servers."""
    _ = config
    httpx.post(
        "https://oauth2.googleapis.com/revoke",
        data={"token": token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
