from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import download_models  # noqa: E402
from common import bool_env  # noqa: E402


def test_civitai_request_includes_authorization_when_configured(monkeypatch):
    monkeypatch.setenv("CIVITAI_API_KEY", "secret-token")
    request = download_models.make_request("https://civitai.com/api/download/models/123")

    assert request.get_header("Authorization") == "Bearer secret-token"


def test_placeholder_auth_values_are_unset(monkeypatch):
    monkeypatch.setenv("CIVITAI_API_KEY", "__unset__")
    monkeypatch.setenv("CIVITAI_TOKEN", " value ")
    request = download_models.make_request("https://civitai.com/api/download/models/123")

    assert request.get_header("Authorization") is None


def test_redirected_non_civitai_request_does_not_include_authorization():
    seen: list[tuple[str, bool]] = []
    storage_port: list[int] = []

    class StorageHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(("storage", bool(self.headers.get("Authorization"))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x")

        def log_message(self, format, *args):  # noqa: A002
            return

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(("initial", bool(self.headers.get("Authorization"))))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{storage_port[0]}/object")
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A002
            return

    storage = ThreadingHTTPServer(("127.0.0.1", 0), StorageHandler)
    storage_port.append(storage.server_address[1])
    initial = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        threading.Thread(target=storage.serve_forever, daemon=True),
        threading.Thread(target=initial.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        request = download_models.make_request(f"http://127.0.0.1:{initial.server_address[1]}/start")
        request.add_header("Authorization", "Bearer redacted")
        with download_models.URL_OPENER.open(request, timeout=5) as response:
            assert response.status == 200
    finally:
        initial.shutdown()
        storage.shutdown()

    assert seen == [("initial", True), ("storage", False)]


def test_download_paths_use_shared_safe_downloader(monkeypatch, tmp_path):
    manifest = {
        "models": [
            {
                "name": "Checkpoint",
                "enabledBy": "DOWNLOAD_CHECKPOINT_7GB",
                "defaultEnabled": True,
                "source": "civitai",
                "downloadHost": "https://civitai.com",
                "versionId": "123",
                "filename": "checkpoint.safetensors",
                "destination": "checkpoints",
                "required": False,
                "approxSize": "7 GB",
                "approxSizeGb": 7.0,
            }
        ]
    }
    calls = []
    monkeypatch.setattr(download_models, "load_json", lambda path: manifest)
    monkeypatch.setattr(download_models, "download", lambda **kwargs: calls.append(kwargs))

    failures = download_models.download_manifest_models(tmp_path, Path("models.json"), dry_run=False)

    assert failures == []
    assert calls[0]["url"] == "https://civitai.com/api/download/models/123"


def test_lora_downloads_use_shared_safe_downloader(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("CIVITAI_LORA_VERSION_IDS", "123")
    monkeypatch.setattr(download_models, "download", lambda **kwargs: calls.append(kwargs))

    failures = download_models.download_loras(tmp_path, dry_run=False)

    assert failures == []
    assert calls[0]["url"] == "https://civitai.com/api/download/models/123"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_bool_env_accepts_forgiving_values(monkeypatch, value, expected):
    monkeypatch.setenv("FLAG", value)
    assert bool_env("FLAG") is expected


def test_bool_env_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("DOWNLOAD_PONY_REALISM_7GB", "maybe")

    with pytest.raises(ValueError, match='Invalid value for DOWNLOAD_PONY_REALISM_7GB: "maybe"'):
        bool_env("DOWNLOAD_PONY_REALISM_7GB")
