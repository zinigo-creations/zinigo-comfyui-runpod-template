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
- Neutral RunPod-facing aliases for Civitai/Hugging Face/FileBrowser auth
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

## RunPod template environment

Copy from `runpod-env.example` into the RunPod template UI. Use the neutral `ZINIGO_*` names there; startup maps them inside the container to the canonical names used by ComfyUI, Civicomfy, and the download scripts.

```text
ZINIGO_CIVITAI_AUTH=__unset__
ZINIGO_HF_AUTH=__unset__
ZINIGO_FILEBROWSER_AUTH=__unset__
ZINIGO_CIVITAI_LORAS=__unset__
ZINIGO_COMFYUI_EXTRA_ARGS=__unset__
```

Set real values directly or use RunPod secret interpolation:

```text
ZINIGO_CIVITAI_AUTH={{ RUNPOD_SECRET_civitai_api_key }}
ZINIGO_HF_AUTH={{ RUNPOD_SECRET_huggingface_token }}
ZINIGO_FILEBROWSER_AUTH={{ RUNPOD_SECRET_filebrowser_password }}
```

`ZINIGO_HF_AUTH` is optional unless you add gated Hugging Face URLs later.

If `ZINIGO_FILEBROWSER_AUTH` is empty or left as `__unset__`, startup generates a random 16-character FileBrowser password and prints it in the Pod logs.

## Environment variables

Alias priority is:

```text
ZINIGO_CIVITAI_AUTH -> CIVITAI_API_KEY and CIVITAI_TOKEN
ZINIGO_HF_AUTH -> HF_TOKEN
ZINIGO_FILEBROWSER_AUTH -> FILEBROWSER_PASSWORD
ZINIGO_CIVITAI_LORAS -> CIVITAI_LORA_VERSION_IDS
ZINIGO_COMFYUI_EXTRA_ARGS -> COMFYUI_ARGS
```

The older canonical env vars still work as fallbacks if supplied directly. Placeholder values are ignored when trimmed, case-insensitively: empty string, `__unset__`, `value`, `none`, `null`, and `undefined`.

### Arbitrary LoRAs

```text
ZINIGO_CIVITAI_LORAS=517898,534952,448977
```

Backward-compatible fallback aliases:

```text
CIVITAI_LORA_VERSION_IDS
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
ZINIGO_COMFYUI_EXTRA_ARGS=__unset__
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
docker build -t zinigocreations/zinigo-comfyui-runpod-template:v0.1.1-cuda12.8 .
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
  zinigocreations/zinigo-comfyui-runpod-template:v0.1.1-cuda12.8
```

Open:

```text
http://localhost:8188
```

## Build and push

Manual build:

```bash
docker build -t YOUR_DOCKERHUB_USERNAME/zinigo-comfyui-runpod-template:v0.1.1-cuda12.8 .
docker push YOUR_DOCKERHUB_USERNAME/zinigo-comfyui-runpod-template:v0.1.1-cuda12.8
```

Or use the included GitHub Action after setting:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

as GitHub repository secrets.

## Important notes

- Civitai tokens are read from environment variables at runtime. They are not written into the image or printed in logs.
- FileBrowser password is reset on each launch if `ZINIGO_FILEBROWSER_AUTH` or `FILEBROWSER_PASSWORD` is supplied.
- If no FileBrowser password is configured, a random password is generated and printed.
- Model downloads use `.part` files and rename after success.
- Existing downloaded files are skipped.
- `FAIL_ON_MODEL_DOWNLOAD_ERROR=true` means enabled model download failures stop startup before ComfyUI launches.
- SSH, Jupyter, and FileBrowser start before model download/setup so you can still debug a failing Pod.
