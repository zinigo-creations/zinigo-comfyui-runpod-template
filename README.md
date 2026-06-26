# Zinigo ComfyUI RunPod Template

A custom RunPod ComfyUI template based on the official `runpod/comfyui:cuda12.8` image.

It keeps the useful RunPod services from the official image:

- ComfyUI on `8188`
- FileBrowser on `8080`
- JupyterLab on `8888`
- SSH on `22`

It adds:

- Bundled workflow JSON files
- Required custom nodes for the bundled workflows
- Civicomfy and ComfyUI-Manager
- Boolean environment flags for checkpoint/model downloads
- Secret-backed Civitai/Hugging Face auth
- Arbitrary Civitai LoRA version ID downloading
- Startup validation for workflow node coverage

## Default RunPod template settings

Use these defaults when creating the RunPod template:

| Setting | Value |
|---|---:|
| Container Disk | `250 GB` |
| Volume Disk | `0 GB` |
| HTTP Port | `8188` |
| FileBrowser Port | `8080` |
| Jupyter Port | `8888` |
| SSH Port | `22` |

Why `250 GB` container disk: the base image, ComfyUI workspace, Python environment, several SDXL/Pony checkpoints, optional upscaler, and output images need breathing room. All bundled checkpoint flags default to `false`, but enabling several Pony checkpoints at once can eat disk quickly. `250 GB` gives you sane headroom without paying for persistent volume storage.

Volume storage is intentionally `0 GB`. It is expensive and can be inconsistent. Enable a RunPod volume only when you specifically want persistence across Pods.

## Required RunPod secrets

Create these in RunPod Secrets and reference them in the template environment variables.

```text
CIVITAI_API_KEY={{ RUNPOD_SECRET_civitai_api_key }}
HF_TOKEN={{ RUNPOD_SECRET_huggingface_token }}
FILEBROWSER_PASSWORD={{ RUNPOD_SECRET_filebrowser_password }}
```

`HF_TOKEN` is optional unless you add gated Hugging Face URLs later.

If `FILEBROWSER_PASSWORD` is empty, startup generates a random 16-character password and prints it in the Pod logs.

## Environment variables

Copy from `runpod-env.example` into the RunPod template.

### Arbitrary LoRAs

```text
CIVITAI_LORA_VERSION_IDS=517898,534952,448977
```

Supported aliases:

```text
LORA_VERSION_IDS
LORAS_IDS_TO_DOWNLOAD
```

These must be Civitai **version IDs**, not model page IDs. They are downloaded to:

```text
/workspace/runpod-slim/ComfyUI/models/loras
```

### Bundled checkpoint flags

All bundled checkpoint flags default to `false`:

```text
DOWNLOAD_AUTISMMIX_SDXL=false
DOWNLOAD_CYBERREALISTIC_PONY=false
DOWNLOAD_PONY_REALISM=false
DOWNLOAD_CYBERREALISTIC_PONY_SEMI_REALISTIC=false
DOWNLOAD_RI_MIX_ILLUSTRIOUS_ANIMA=false
DOWNLOAD_MIAOMIAO_3D_HAREM=false
DOWNLOAD_BABES=false
DOWNLOAD_REALISM_BY_STABLE_YOGI_PONY=false
```

Optional upscaler referenced by the bundled workflow:

```text
DOWNLOAD_4X_ULTRASHARP=false
```

### Setup behavior

```text
RUN_STARTUP_VALIDATION=true
FAIL_ON_MODEL_DOWNLOAD_ERROR=true
CUSTOM_NODES_UPDATE_ON_START=false
COMFYUI_ARGS=
```

`CUSTOM_NODES_UPDATE_ON_START=false` is intentional. Rebuild the image when you want newer custom nodes. Do not make every Pod launch a moving target.

## Included models

The model manifest lives at:

```text
config/models.json
```

All named checkpoint downloads go to:

```text
/workspace/runpod-slim/ComfyUI/models/checkpoints
```

Civitai version IDs are used directly. Filenames are the readable slugs from the URLs you supplied.

| Env flag | Filename |
|---|---|
| `DOWNLOAD_AUTISMMIX_SDXL` | `autismmix-sdxl.safetensors` |
| `DOWNLOAD_CYBERREALISTIC_PONY` | `cyberrealistic-pony.safetensors` |
| `DOWNLOAD_PONY_REALISM` | `pony-realism.safetensors` |
| `DOWNLOAD_CYBERREALISTIC_PONY_SEMI_REALISTIC` | `cyberrealistic-pony-semi-realistic.safetensors` |
| `DOWNLOAD_RI_MIX_ILLUSTRIOUS_ANIMA` | `ri-mix-illustrious-anima.safetensors` |
| `DOWNLOAD_MIAOMIAO_3D_HAREM` | `miaomiao-3d-harem.safetensors` |
| `DOWNLOAD_BABES` | `babes.safetensors` |
| `DOWNLOAD_REALISM_BY_STABLE_YOGI_PONY` | `realism-by-stable-yogi-pony.safetensors` |
| `DOWNLOAD_4X_ULTRASHARP` | `4x-UltraSharp.pth` |

## Bundled custom nodes

The custom node manifest lives at:

```text
config/custom-nodes.json
```

Included/ensured:

- `ComfyUI-Manager`
- `Civicomfy`
- `rgthree-comfy`
- `ComfyUI-Addoor`

The base `runpod/comfyui:cuda12.8` image already includes ComfyUI-Manager and Civicomfy, but this template still validates/ensures them so the workflow setup does not silently drift.

## Bundled workflows

Workflow files live in:

```text
workflows/
```

At startup they are copied to:

```text
/workspace/runpod-slim/ComfyUI/user/default/workflows/zinigo
/workspace/workflows/zinigo
```

The first path is for ComfyUI's user workflow area. The second path makes them easy to find in FileBrowser.

## Local test

Basic validation without Docker:

```bash
make validate
```

Docker build:

```bash
docker build -t zinigofast/comfyui-runpod:dev-cuda12.8 .
```

Local run, if Docker has GPU access:

```bash
docker run --gpus all --rm -it \
  -p 8188:8188 \
  -p 8080:8080 \
  -p 8888:8888 \
  -p 2222:22 \
  --env-file runpod-env.example \
  -v comfy-workspace:/workspace \
  zinigofast/comfyui-runpod:dev-cuda12.8
```

Open:

```text
http://localhost:8188
```

## Build and push

Manual build:

```bash
docker build -t YOUR_DOCKERHUB_USERNAME/comfyui-runpod:v1-cuda12.8 .
docker push YOUR_DOCKERHUB_USERNAME/comfyui-runpod:v1-cuda12.8
```

Or use the included GitHub Action after setting:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

as GitHub repository secrets.

## Important notes

- Civitai tokens are read from environment variables at runtime. They are not written into the image.
- FileBrowser password is reset on each launch if `FILEBROWSER_PASSWORD` is supplied.
- If `FILEBROWSER_PASSWORD` is empty, a random password is generated and printed.
- Model downloads use `.part` files and rename after success.
- Existing downloaded files are skipped.
- `FAIL_ON_MODEL_DOWNLOAD_ERROR=true` means enabled model download failures stop startup before ComfyUI launches.
- SSH, Jupyter, and FileBrowser start before model download/setup so you can still debug a failing Pod.
