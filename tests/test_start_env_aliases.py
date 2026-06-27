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


def test_zinigo_aliases_take_priority_and_set_canonical_vars():
    run_bash(
        r"""
        set -euo pipefail
        source ./start.sh

        export ZINIGO_CIVITAI_AUTH=' alias-token '
        export CIVITAI_API_KEY='old-key'
        export CIVITAI_TOKEN='old-token'
        export ZINIGO_HF_AUTH='alias-hf'
        export HF_TOKEN='old-hf'
        export ZINIGO_FILEBROWSER_AUTH='alias-filebrowser'
        export FILEBROWSER_PASSWORD='old-filebrowser'
        export ZINIGO_CIVITAI_LORAS='101, 202'
        export CIVITAI_LORA_VERSION_IDS='303'
        export ZINIGO_COMFYUI_EXTRA_ARGS='--lowvram'
        export COMFYUI_ARGS='--cpu'

        normalize_runpod_env_aliases >/dev/null

        [ "$CIVITAI_API_KEY" = 'alias-token' ]
        [ "$CIVITAI_TOKEN" = 'alias-token' ]
        [ "$HF_TOKEN" = 'alias-hf' ]
        [ "$FILEBROWSER_PASSWORD" = 'alias-filebrowser' ]
        [ "$CIVITAI_LORA_VERSION_IDS" = '101, 202' ]
        [ "$COMFYUI_ARGS" = '--lowvram' ]
        """
    )


def test_placeholders_are_ignored_and_old_vars_fall_back():
    run_bash(
        r"""
        set -euo pipefail
        source ./start.sh

        export ZINIGO_CIVITAI_AUTH=' __UNSET__ '
        export CIVITAI_API_KEY='old-key'
        export ZINIGO_HF_AUTH='value'
        export HF_TOKEN='old-hf'
        export ZINIGO_FILEBROWSER_AUTH=' NONE '
        export FILEBROWSER_PASSWORD='old-filebrowser'
        export ZINIGO_CIVITAI_LORAS='null'
        export LORA_VERSION_IDS='404'
        export ZINIGO_COMFYUI_EXTRA_ARGS='undefined'
        export COMFYUI_ARGS='--cpu'

        normalize_runpod_env_aliases >/dev/null

        [ "$CIVITAI_API_KEY" = 'old-key' ]
        [ "$CIVITAI_TOKEN" = 'old-key' ]
        [ "$HF_TOKEN" = 'old-hf' ]
        [ "$FILEBROWSER_PASSWORD" = 'old-filebrowser' ]
        [ "$CIVITAI_LORA_VERSION_IDS" = '404' ]
        [ "$COMFYUI_ARGS" = '--cpu' ]
        """
    )


def test_placeholder_only_values_unset_canonical_vars():
    run_bash(
        r"""
        set -euo pipefail
        source ./start.sh

        export ZINIGO_CIVITAI_AUTH='null'
        export CIVITAI_API_KEY='undefined'
        export CIVITAI_TOKEN='value'
        export ZINIGO_HF_AUTH='__unset__'
        export HF_TOKEN='none'
        export ZINIGO_FILEBROWSER_AUTH=''
        export FILEBROWSER_PASSWORD='null'
        export ZINIGO_CIVITAI_LORAS='value'
        export CIVITAI_LORA_VERSION_IDS='none'
        export ZINIGO_COMFYUI_EXTRA_ARGS='undefined'
        export COMFYUI_ARGS='__unset__'

        normalize_runpod_env_aliases >/dev/null

        [ -z "${CIVITAI_API_KEY+x}" ]
        [ -z "${CIVITAI_TOKEN+x}" ]
        [ -z "${HF_TOKEN+x}" ]
        [ -z "${FILEBROWSER_PASSWORD+x}" ]
        [ -z "${CIVITAI_LORA_VERSION_IDS+x}" ]
        [ -z "${COMFYUI_ARGS+x}" ]
        """
    )
