from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

MODEL_DIRS = {
    "checkpoints": "models/checkpoints",
    "loras": "models/loras",
    "vae": "models/vae",
    "text_encoders": "models/text_encoders",
    "clip": "models/clip",
    "clip_vision": "models/clip_vision",
    "diffusion_models": "models/diffusion_models",
    "unet": "models/diffusion_models",
    "controlnet": "models/controlnet",
    "upscale_models": "models/upscale_models",
    "embeddings": "models/embeddings",
}


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    raise ValueError(
        f'Invalid value for {name}: "{raw}". '
        "Use true or false."
    )


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def comfyui_dir() -> Path:
    return Path(os.environ.get("COMFYUI_DIR", "/workspace/runpod-slim/ComfyUI")).resolve()


def template_dir() -> Path:
    return Path(os.environ.get("ZINIGO_TEMPLATE_DIR", "/opt/zinigo-comfyui-template")).resolve()


def destination_path(root: Path, destination: str) -> Path:
    try:
        relative = MODEL_DIRS[destination]
    except KeyError as error:
        supported = ", ".join(sorted(MODEL_DIRS))
        raise ValueError(f"Unknown destination {destination!r}. Supported: {supported}") from error
    return root / relative


def split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    items = re.split(r"[\s,;]+", raw.strip())
    return [item for item in items if item]
