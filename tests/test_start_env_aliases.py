from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_bash(script: str) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")

    try:
        subprocess.run(
            [bash, "--version"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"bash is not usable: {exc}")

    subprocess.run([bash, "-lc", script], cwd=ROOT, check=True, text=True, capture_output=True)


def test_public_env_names_set_canonical_vars():
    run_bash(
        r"""
        set -euo pipefail
        source ./start.sh

        export CIVITAI_AUTH=' civitai-token '
        export HUGGINGFACE_AUTH='hf-token'
        export FILEBROWSER_AUTH='filebrowser-password'
        export CIVITAI_LORA_VERSION_IDS='101, 202'
        export COMFYUI_ARGS='--lowvram'

        normalize_runpod_env_aliases >/dev/null

        [ "$CIVITAI_API_KEY" = 'civitai-token' ]
        [ "$CIVITAI_TOKEN" = 'civitai-token' ]
        [ "$HF_TOKEN" = 'hf-token' ]
        [ "$FILEBROWSER_PASSWORD" = 'filebrowser-password' ]
        [ "$CIVITAI_LORA_VERSION_IDS" = '101, 202' ]
        [ "$COMFYUI_ARGS" = '--lowvram' ]
        """
    )


def test_placeholders_are_ignored_and_unset_canonical_vars():
    run_bash(
        r"""
        set -euo pipefail
        source ./start.sh

        export CIVITAI_AUTH=' __UNSET__ '
        export HUGGINGFACE_AUTH='value'
        export FILEBROWSER_AUTH=' NONE '
        export CIVITAI_LORA_VERSION_IDS='null'
        export COMFYUI_ARGS='undefined'

        normalize_runpod_env_aliases >/dev/null

        [ -z "${CIVITAI_API_KEY+x}" ]
        [ -z "${CIVITAI_TOKEN+x}" ]
        [ -z "${HF_TOKEN+x}" ]
        [ -z "${FILEBROWSER_PASSWORD+x}" ]
        [ -z "${CIVITAI_LORA_VERSION_IDS+x}" ]
        [ -z "${COMFYUI_ARGS+x}" ]
        """
    )
