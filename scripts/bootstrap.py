#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from common import bool_env, comfyui_dir, template_dir


def run(cmd: list[str], check: bool = True) -> int:
    print("$", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, text=True)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)
    return completed.returncode


def copy_workflows(template: Path, comfyui: Path) -> None:
    source = template / "workflows"
    targets = [
        comfyui / "user" / "default" / "workflows" / "zinigo",
        Path("/workspace") / "workflows" / "zinigo",
    ]

    for workflow in sorted(source.glob("*.json")):
        for target_dir in targets:
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / workflow.name
            shutil.copy2(workflow, target)
            print(f"Workflow copied: {target}")


def ensure_directories(comfyui: Path) -> None:
    for rel in [
        "models/checkpoints",
        "models/loras",
        "models/vae",
        "models/text_encoders",
        "models/clip",
        "models/clip_vision",
        "models/diffusion_models",
        "models/controlnet",
        "models/upscale_models",
        "models/embeddings",
        "input",
        "output",
        "temp",
        "user/default/workflows",
    ]:
        path = comfyui / rel
        path.mkdir(parents=True, exist_ok=True)


def maybe_validate_comfy_start(comfyui: Path, python_bin: str) -> None:
    if not bool_env("RUN_STARTUP_VALIDATION", True):
        print("RUN_STARTUP_VALIDATION=false; skipping ComfyUI import check.")
        return

    print("Running ComfyUI quick startup validation...")
    run([python_bin, "main.py", "--quick-test-for-ci"], check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui", type=Path, default=comfyui_dir())
    parser.add_argument("--template", type=Path, default=template_dir())
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    comfyui = args.comfyui.resolve()
    template = args.template.resolve()
    python_bin = args.python

    print(f"Bootstrap template dir: {template}")
    print(f"Bootstrap ComfyUI dir: {comfyui}")

    ensure_directories(comfyui)
    copy_workflows(template, comfyui)

    run(
        [
            python_bin,
            str(template / "scripts" / "install_custom_nodes.py"),
            "--comfyui",
            str(comfyui),
            "--manifest",
            str(template / "config" / "custom-nodes.json"),
            "--install-deps",
        ]
    )

    run(
        [
            python_bin,
            str(template / "scripts" / "validate_workflows.py"),
            "--workflows",
            str(template / "workflows"),
            "--custom-nodes",
            str(template / "config" / "custom-nodes.json"),
        ]
    )

    run(
        [
            python_bin,
            str(template / "scripts" / "download_models.py"),
            "--comfyui",
            str(comfyui),
            "--manifest",
            str(template / "config" / "models.json"),
        ]
    )

    cwd = Path.cwd()
    try:
        os.chdir(comfyui)
        maybe_validate_comfy_start(comfyui, python_bin)
    finally:
        os.chdir(cwd)

    print("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
