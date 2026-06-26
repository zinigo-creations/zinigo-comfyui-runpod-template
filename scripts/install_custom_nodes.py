#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from common import bool_env, load_json


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, check=check)


def git_current_ref(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(path),
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def ensure_repo(custom_nodes_dir: Path, item: dict, update_on_start: bool) -> Path:
    target = custom_nodes_dir / item["directory"]
    repo = item["repo"]
    ref = item.get("ref") or "main"

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(target)])
    elif (target / ".git").exists():
        print(f"Custom node already present: {target.name}")
        if update_on_start:
            run(["git", "fetch", "origin", ref, "--depth", "1"], cwd=target)
            run(["git", "checkout", ref], cwd=target)
            run(["git", "pull", "--ff-only", "origin", ref], cwd=target, check=False)
    else:
        print(f"Custom node directory exists but is not a git repo: {target}")

    return target


def install_requirements(node_dir: Path, python_bin: str) -> None:
    req = node_dir / "requirements.txt"
    if req.exists():
        print(f"Installing requirements for {node_dir.name}")
        run([python_bin, "-m", "pip", "install", "-r", str(req)])

    install_py = node_dir / "install.py"
    if install_py.exists():
        print(f"Running install.py for {node_dir.name}")
        run([python_bin, str(install_py)], cwd=node_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    comfyui = args.comfyui.resolve()
    manifest = load_json(args.manifest)
    custom_nodes_dir = comfyui / "custom_nodes"
    custom_nodes_dir.mkdir(parents=True, exist_ok=True)

    update_on_start = args.update or bool_env("CUSTOM_NODES_UPDATE_ON_START", False)

    for item in manifest["nodes"]:
        node_dir = ensure_repo(custom_nodes_dir, item, update_on_start)
        if args.install_deps:
            install_requirements(node_dir, args.python)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
