#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import load_json, template_dir

BUILTIN_NODE_TYPES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "VAELoader",
    "VAEEncode",
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "SaveImage",
    "LoadImage",
    "PreviewImage",
}

FRONTEND_OR_VIRTUAL_TYPES = set()


def node_provider_map(custom_nodes_manifest: Path) -> dict[str, str]:
    manifest = load_json(custom_nodes_manifest)
    providers: dict[str, str] = {}
    for item in manifest["nodes"]:
        for node_type in item.get("requiredNodeTypes", []):
            providers[node_type] = item["name"]
    return providers


def workflow_node_types(path: Path) -> set[str]:
    data = load_json(path)
    return {node["type"] for node in data.get("nodes", []) if "type" in node}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflows", type=Path, default=template_dir() / "workflows")
    parser.add_argument("--custom-nodes", type=Path, default=template_dir() / "config" / "custom-nodes.json")
    args = parser.parse_args()

    providers = node_provider_map(args.custom_nodes)
    workflow_files = sorted(args.workflows.glob("*.json"))
    if not workflow_files:
        print(f"No workflow JSON files found in {args.workflows}")
        return 1

    failed = False
    for workflow in workflow_files:
        types = workflow_node_types(workflow)
        missing = sorted(
            node_type
            for node_type in types
            if node_type not in BUILTIN_NODE_TYPES
            and node_type not in providers
            and node_type not in FRONTEND_OR_VIRTUAL_TYPES
        )
        print(f"{workflow.name}: {len(types)} node type(s)")
        for node_type in sorted(types):
            provider = "builtin" if node_type in BUILTIN_NODE_TYPES else providers.get(node_type, "UNKNOWN")
            print(f"  - {node_type}: {provider}")
        if missing:
            failed = True
            print("  Missing provider mapping:")
            for node_type in missing:
                print(f"    * {node_type}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
