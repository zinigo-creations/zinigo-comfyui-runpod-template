#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import download_models

USER_AGENT = "ZinigoRunPodComfyTemplate/diagnostic"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoggingHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        print(f"request host={host(req.full_url)} auth={has_auth(req)}")
        return super().https_open(req)


def host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def has_auth(req: urllib.request.Request) -> bool:
    return bool(req.get_header("Authorization") or req.get_header("authorization"))


def make_request(url: str, auth: str | None, byte_range: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if auth:
        headers["Authorization"] = auth
    if byte_range:
        headers["Range"] = byte_range
    return urllib.request.Request(url, headers=headers)


def status_with_opener(opener, req: urllib.request.Request) -> tuple[int, dict[str, str], str | None]:
    try:
        with opener.open(req, timeout=30) as response:
            return response.status, dict(response.headers.items()), None
    except urllib.error.HTTPError as error:
        body = error.read(400).decode("utf-8", errors="replace").strip()
        return error.code, dict(error.headers.items()), body


def manual_redirect_chain(url: str, auth: str | None, max_redirects: int) -> list[tuple[str, int, bool, str | None]]:
    opener = urllib.request.build_opener(NoRedirect)
    chain: list[tuple[str, int, bool, str | None]] = []
    current = url

    for _ in range(max_redirects + 1):
        req = make_request(current, auth)
        status, headers, _ = status_with_opener(opener, req)
        location = headers.get("Location") or headers.get("location")
        next_url = urllib.parse.urljoin(current, location) if location else None
        chain.append((host(current), status, has_auth(req), host(next_url) if next_url else None))
        if not next_url or status not in {301, 302, 303, 307, 308}:
            break
        current = next_url

    return chain


def final_redirect_url(url: str, auth: str | None, max_redirects: int) -> str:
    opener = urllib.request.build_opener(NoRedirect)
    current = url

    for _ in range(max_redirects):
        req = make_request(current, auth)
        status, headers, _ = status_with_opener(opener, req)
        location = headers.get("Location") or headers.get("location")
        if not location or status not in {301, 302, 303, 307, 308}:
            return current
        current = urllib.parse.urljoin(current, location)

    return current


def probe_storage(url: str, auth: str | None) -> tuple[int, str | None]:
    opener = urllib.request.build_opener(NoRedirect)
    req = make_request(url, auth, byte_range="bytes=0-0")
    status, _, body = status_with_opener(opener, req)
    return status, body


def urllib_default_redirect_probe(url: str, auth: str | None) -> tuple[int | None, str | None]:
    opener = urllib.request.build_opener(LoggingHTTPSHandler)
    try:
        req = make_request(url, auth, byte_range="bytes=0-0")
        with opener.open(req, timeout=30) as response:
            return response.status, None
    except urllib.error.HTTPError as error:
        return error.code, error.read(400).decode("utf-8", errors="replace").strip()
    except Exception as error:  # noqa: BLE001 - diagnostic should report transport failures
        return None, f"{type(error).__name__}: {error}"


def local_redirect_simulation() -> int:
    events: list[tuple[str, bool]] = []
    storage_port: list[int] = []

    class StorageHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            auth_present = bool(self.headers.get("Authorization"))
            events.append(("storage.local", auth_present))
            if auth_present:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing x-amz-content-sha256")
            else:
                self.send_response(206)
                self.send_header("Content-Range", "bytes 0-0/1")
                self.end_headers()
                self.wfile.write(b"x")

        def log_message(self, format, *args):  # noqa: A002
            return

    class InitialHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            events.append(("civitai.local", bool(self.headers.get("Authorization"))))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{storage_port[0]}/signed-storage-object")
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A002
            return

    storage = ThreadingHTTPServer(("127.0.0.1", 0), StorageHandler)
    storage_port.append(storage.server_address[1])
    initial = ThreadingHTTPServer(("127.0.0.1", 0), InitialHandler)

    threads = [
        threading.Thread(target=storage.serve_forever, daemon=True),
        threading.Thread(target=initial.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()

    initial_url = f"http://127.0.0.1:{initial.server_address[1]}/api/download/models/diagnostic"
    auth = "Bearer diagnostic-redacted"
    status, body = urllib_default_redirect_probe(initial_url, auth)

    storage_url = f"http://127.0.0.1:{storage_port[0]}/signed-storage-object"
    without_auth_status, without_auth_body = probe_storage(storage_url, None)
    with_auth_status, with_auth_body = probe_storage(storage_url, auth)

    print("local redirect simulation:")
    for idx, (event_host, auth_present) in enumerate(events, start=1):
        print(f"{idx}. host={event_host} auth={auth_present}")
    print(f"default_redirect_status={status}")
    if body:
        print(f"default_redirect_body={body}")
    print(f"storage_without_auth_status={without_auth_status}")
    if without_auth_body:
        print(f"storage_without_auth_body={without_auth_body}")
    print(f"storage_with_auth_status={with_auth_status}")
    if with_auth_body:
        print(f"storage_with_auth_body={with_auth_body}")

    events.clear()
    safe_request = make_request(initial_url, auth, byte_range="bytes=0-0")
    try:
        with download_models.URL_OPENER.open(safe_request, timeout=30) as response:
            safe_status = response.status
            safe_body = None
    except urllib.error.HTTPError as error:
        safe_status = error.code
        safe_body = error.read(400).decode("utf-8", errors="replace").strip()

    print("project safe redirect simulation:")
    for idx, (event_host, auth_present) in enumerate(events, start=1):
        print(f"{idx}. host={event_host} auth={auth_present}")
    print(f"safe_redirect_status={safe_status}")
    if safe_body:
        print(f"safe_redirect_body={safe_body}")

    initial.shutdown()
    storage.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version_id", nargs="?")
    parser.add_argument("--host", default="https://civitai.com")
    parser.add_argument("--max-redirects", type=int, default=10)
    parser.add_argument("--local-simulate", action="store_true")
    parser.add_argument(
        "--auth-mode",
        choices=["none", "dummy", "env"],
        default="dummy",
        help="Use dummy auth by default; never prints the auth value.",
    )
    args = parser.parse_args()

    if args.local_simulate:
        return local_redirect_simulation()

    if not args.version_id:
        parser.error("version_id is required unless --local-simulate is used")

    auth = None
    if args.auth_mode == "dummy":
        auth = "Bearer diagnostic-redacted"
    elif args.auth_mode == "env":
        token = os.environ.get("CIVITAI_API_KEY") or os.environ.get("CIVITAI_TOKEN")
        auth = f"Bearer {token}" if token else None

    url = f"{args.host.rstrip('/')}/api/download/models/{args.version_id}"

    print("manual redirect chain:")
    for idx, (request_host, status, auth_present, location_host) in enumerate(
        manual_redirect_chain(url, auth, args.max_redirects),
        start=1,
    ):
        print(
            f"{idx}. host={request_host} status={status} "
            f"auth={auth_present} location_host={location_host or '-'}"
        )

    final_url = final_redirect_url(url, auth, args.max_redirects)
    final_host = host(final_url)
    print(f"final_host={final_host}")

    no_auth_status, no_auth_body = probe_storage(final_url, None)
    with_auth_status, with_auth_body = probe_storage(final_url, "Bearer diagnostic-redacted")
    print(f"final_url_without_auth status={no_auth_status}")
    if no_auth_body:
        print(f"final_url_without_auth body={no_auth_body}")
    print(f"final_url_with_auth status={with_auth_status}")
    if with_auth_body:
        print(f"final_url_with_auth body={with_auth_body}")

    print("urllib default redirect probe:")
    default_status, default_body = urllib_default_redirect_probe(url, auth)
    print(f"default_redirect_status={default_status}")
    if default_body:
        print(f"default_redirect_body={default_body}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
