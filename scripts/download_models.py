#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from pathlib import Path

from common import bool_env, comfyui_dir, destination_path, load_json, split_ids, template_dir

USER_AGENT = "ZinigoRunPodComfyTemplate/1.0"
CHUNK_SIZE = 1024 * 1024 * 4


def token_for_host(host: str) -> str | None:
    lowered = host.lower()
    if "civitai" in lowered:
        return os.environ.get("CIVITAI_API_KEY") or os.environ.get("CIVITAI_TOKEN")
    if "huggingface" in lowered or "hf.co" in lowered:
        return os.environ.get("HF_TOKEN")
    return None


def auth_header_name(host: str) -> str:
    return "Authorization"


def make_request(url: str, start_byte: int = 0) -> urllib.request.Request:
    parsed = urllib.parse.urlparse(url)
    headers = {"User-Agent": USER_AGENT}
    token = token_for_host(parsed.netloc)
    if token:
        headers[auth_header_name(parsed.netloc)] = f"Bearer {token}"
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"
    return urllib.request.Request(url, headers=headers)


def content_disposition_filename(header: str | None) -> str | None:
    if not header:
        return None

    msg = Message()
    msg["content-disposition"] = header
    filename = msg.get_param("filename", header="content-disposition")
    if filename:
        return Path(filename).name

    match = re.search(r"filename\*=UTF-8''([^;]+)", header, re.IGNORECASE)
    if match:
        return Path(urllib.parse.unquote(match.group(1))).name

    match = re.search(r'filename="?([^";]+)"?', header, re.IGNORECASE)
    if match:
        return Path(match.group(1)).name

    return None


def safe_filename(name: str, fallback: str) -> str:
    name = Path(name or fallback).name.strip()
    name = re.sub(r"[^A-Za-z0-9._+()\- ]+", "-", name).strip(" .-")
    return name or fallback


def download(url: str, target_dir: Path, filename: str | None, fallback_name: str, required: bool) -> Path | None:
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / safe_filename(filename, fallback_name) if filename else None
    partial = None

    if target and target.exists() and target.stat().st_size > 0:
        print(f"Already exists, skipping: {target}")
        return target

    for attempt in range(1, 6):
        try:
            start_byte = 0
            if target:
                partial = target.with_suffix(target.suffix + ".part")
                start_byte = partial.stat().st_size if partial.exists() else 0

            req = make_request(url, start_byte=start_byte)
            with urllib.request.urlopen(req, timeout=120) as response:
                status = getattr(response, "status", 200)

                if status == 200 and start_byte and partial:
                    print("Server did not honor resume request; restarting partial download.")
                    partial.unlink(missing_ok=True)
                    start_byte = 0

                if not target:
                    header_name = content_disposition_filename(response.headers.get("content-disposition"))
                    target = target_dir / safe_filename(header_name or fallback_name, fallback_name)
                    partial = target.with_suffix(target.suffix + ".part")
                    if target.exists() and target.stat().st_size > 0:
                        print(f"Already exists, skipping: {target}")
                        return target

                mode = "ab" if start_byte and status == 206 else "wb"
                content_length = response.headers.get("content-length")
                total = int(content_length) + start_byte if content_length and content_length.isdigit() else None
                downloaded = start_byte
                last_print = 0.0

                assert partial is not None
                with partial.open(mode + "b") as handle:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if now - last_print > 1:
                            if total:
                                pct = downloaded / total * 100
                                print(
                                    f"  {target.name}: {downloaded / 1024 / 1024:,.1f} MB / "
                                    f"{total / 1024 / 1024:,.1f} MB ({pct:.1f}%)",
                                    flush=True,
                                )
                            else:
                                print(f"  {target.name}: {downloaded / 1024 / 1024:,.1f} MB", flush=True)
                            last_print = now

                partial.replace(target)
                print(f"Saved: {target}")
                return target

        except urllib.error.HTTPError as error:
            detail = error.read(400).decode("utf-8", errors="replace")
            message = f"HTTP {error.code} while downloading {url}: {detail}"
        except Exception as error:  # noqa: BLE001 - startup script should log every failure clearly
            message = f"{type(error).__name__} while downloading {url}: {error}"

        if attempt == 5:
            if required:
                raise RuntimeError(message)
            print(f"WARNING: {message}", file=sys.stderr)
            return None

        delay = min(2 ** attempt, 20)
        print(f"Attempt {attempt} failed: {message}", file=sys.stderr)
        print(f"Retrying in {delay}s...", file=sys.stderr)
        time.sleep(delay)

    return None


def civitai_download_url(host: str, version_id: str) -> str:
    return f"{host.rstrip('/')}/api/download/models/{version_id}"


def model_enabled(item: dict) -> bool:
    if bool_env("DOWNLOAD_ALL_MODELS", False):
        return True
    return bool_env(item["enabledBy"], bool(item.get("defaultEnabled", False)))


def download_manifest_models(comfyui: Path, manifest_path: Path, dry_run: bool) -> list[str]:
    manifest = load_json(manifest_path)
    failures: list[str] = []

    for item in manifest["models"]:
        enabled = model_enabled(item)
        if not enabled:
            print(f"SKIP {item['name']} ({item['enabledBy']}=false)")
            continue

        target_dir = destination_path(comfyui, item["destination"])
        required = bool(item.get("required", False)) or bool_env("FAIL_ON_MODEL_DOWNLOAD_ERROR", True)

        if item["source"] == "civitai":
            url = civitai_download_url(item.get("downloadHost", "https://civitai.com"), str(item["versionId"]))
        elif item["source"] == "direct":
            url = item["url"]
        else:
            raise ValueError(f"Unsupported model source: {item['source']}")

        print(f"DOWNLOAD {item['name']} -> {target_dir / item['filename']}")
        if dry_run:
            continue

        try:
            download(
                url=url,
                target_dir=target_dir,
                filename=item.get("filename"),
                fallback_name=item.get("filename") or f"{item['name']}.safetensors",
                required=required,
            )
        except Exception as error:  # noqa: BLE001
            failures.append(f"{item['name']}: {error}")

    return failures


def lora_ids_from_env() -> list[str]:
    raw = (
        os.environ.get("CIVITAI_LORA_VERSION_IDS")
        or os.environ.get("LORA_VERSION_IDS")
        or os.environ.get("LORAS_IDS_TO_DOWNLOAD")
        or ""
    )
    ids = split_ids(raw)
    invalid = [item for item in ids if not item.isdigit()]
    if invalid:
        raise ValueError(f"Invalid Civitai LoRA version IDs: {', '.join(invalid)}")
    return ids


def download_loras(comfyui: Path, dry_run: bool) -> list[str]:
    failures: list[str] = []
    ids = lora_ids_from_env()
    if not ids:
        print("No CIVITAI_LORA_VERSION_IDS supplied; skipping arbitrary LoRA downloads.")
        return failures

    target_dir = destination_path(comfyui, "loras")
    required = bool_env("FAIL_ON_MODEL_DOWNLOAD_ERROR", True)
    host = os.environ.get("CIVITAI_LORA_DOWNLOAD_HOST", "https://civitai.com")

    for version_id in ids:
        url = civitai_download_url(host, version_id)
        print(f"DOWNLOAD LoRA version {version_id} -> {target_dir}")
        if dry_run:
            continue
        try:
            download(
                url=url,
                target_dir=target_dir,
                filename=None,
                fallback_name=f"civitai-lora-{version_id}.safetensors",
                required=required,
            )
        except Exception as error:  # noqa: BLE001
            failures.append(f"LoRA {version_id}: {error}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui", type=Path, default=comfyui_dir())
    parser.add_argument("--manifest", type=Path, default=template_dir() / "config" / "models.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.comfyui.exists():
        raise SystemExit(f"ComfyUI directory does not exist: {args.comfyui}")

    failures = []
    failures.extend(download_manifest_models(args.comfyui, args.manifest, args.dry_run))
    failures.extend(download_loras(args.comfyui, args.dry_run))

    if failures:
        print("\nModel setup failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    free = shutil.disk_usage(args.comfyui).free / 1024 / 1024 / 1024
    print(f"Model setup complete. Free disk near ComfyUI: {free:.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
