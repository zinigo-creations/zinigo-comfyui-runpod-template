from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_models_have_unique_env_flags_and_filenames():
    manifest = load_json(ROOT / "config" / "models.json")
    flags = [item["enabledBy"] for item in manifest["models"]]
    filenames = [item["filename"] for item in manifest["models"]]
    assert len(flags) == len(set(flags))
    assert len(filenames) == len(set(filenames))
    assert all(item["approxSize"] for item in manifest["models"])
    assert all(float(item["approxSizeGb"]) > 0 for item in manifest["models"])
    assert all(flag.endswith(("GB", "MB")) for flag in flags)


def test_workflow_node_types_are_mapped():
    builtin = {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "UpscaleModelLoader",
        "ImageUpscaleWithModel",
        "SaveImage",
    }
    custom_manifest = load_json(ROOT / "config" / "custom-nodes.json")
    provided = set()
    for item in custom_manifest["nodes"]:
        provided.update(item.get("requiredNodeTypes", []))

    for workflow in (ROOT / "workflows").glob("*.json"):
        data = load_json(workflow)
        workflow_types = {node["type"] for node in data["nodes"]}
        missing = workflow_types - builtin - provided
        assert missing == set()
