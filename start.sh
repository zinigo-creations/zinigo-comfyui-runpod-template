#!/bin/bash
set -e

COMFYUI_DIR="${COMFYUI_DIR:-/workspace/runpod-slim/ComfyUI}"
VENV_DIR="${VENV_DIR:-$COMFYUI_DIR/.venv-cu128}"
OLD_VENV_DIR="$COMFYUI_DIR/.venv"
DB_FILE="${FILEBROWSER_DB:-/workspace/runpod-slim/filebrowser.db}"
TEMPLATE_DIR="${ZINIGO_TEMPLATE_DIR:-/opt/zinigo-comfyui-template}"
ARGS_FILE="/workspace/runpod-slim/comfyui_args.txt"
SETUP_LOG="/workspace/runpod-slim/zinigo-template-setup.log"
TEMPLATE_VERSION="${TEMPLATE_VERSION:-v0.1.3-cuda12.8}"

log() {
    echo "[$(date -Iseconds)] $*"
}

banner() {
    echo "============================================================"
    echo "Zinigo ComfyUI RunPod Template ${TEMPLATE_VERSION}"
    echo "============================================================"
    echo
}

section() {
    echo
    echo "[$1] $2"
}

status_ok() {
    echo "  + $*"
}

status_note() {
    echo "  - $*"
}

random_password() {
    # 16 chars, alphanumeric + shell-safe special characters.
    LC_ALL=C tr -dc 'A-Za-z0-9@#%^+=_-' < /dev/urandom | head -c 16
}

normalized_env_value() {
    local value="${1-}"
    local lowered

    value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    lowered="${value,,}"

    case "$lowered" in
        ""|"__unset__"|"value"|"none"|"null"|"undefined")
            return 1
            ;;
    esac

    printf '%s' "$value"
}

first_real_env_value() {
    local name
    local value

    for name in "$@"; do
        if value="$(normalized_env_value "${!name-}")"; then
            printf '%s' "$value"
            return 0
        fi
    done

    return 1
}

normalize_runpod_env_aliases() {
    local value

    if value="$(first_real_env_value CIVITAI_AUTH)"; then
        export CIVITAI_API_KEY="$value"
        export CIVITAI_TOKEN="$value"
        status_ok "CIVITAI_AUTH configured"
    else
        unset CIVITAI_API_KEY CIVITAI_TOKEN
        status_note "CIVITAI_AUTH not configured"
    fi

    if value="$(first_real_env_value HUGGINGFACE_AUTH)"; then
        export HF_TOKEN="$value"
        status_ok "HUGGINGFACE_AUTH configured"
    else
        unset HF_TOKEN
        status_note "HUGGINGFACE_AUTH not configured"
    fi

    if value="$(first_real_env_value FILEBROWSER_AUTH)"; then
        export FILEBROWSER_PASSWORD="$value"
        status_ok "FileBrowser password configured"
    else
        unset FILEBROWSER_PASSWORD
        status_note "FileBrowser password not configured; one will be generated"
    fi

    if value="$(first_real_env_value CIVITAI_LORA_VERSION_IDS)"; then
        export CIVITAI_LORA_VERSION_IDS="$value"
        status_ok "CIVITAI_LORA_VERSION_IDS configured"
    else
        unset CIVITAI_LORA_VERSION_IDS
        status_note "CIVITAI_LORA_VERSION_IDS not configured"
    fi

    if value="$(first_real_env_value COMFYUI_ARGS)"; then
        export COMFYUI_ARGS="$value"
        status_ok "COMFYUI_ARGS configured"
    else
        unset COMFYUI_ARGS
        status_note "COMFYUI_ARGS not configured"
    fi
}

log_storage_summary() {
    local available
    available="$(df -h /workspace 2>/dev/null | awk 'NR==2 {print $4}')"
    if [ -n "$available" ]; then
        status_ok "Container disk available: $available"
    else
        status_note "Container disk availability unknown"
    fi
    status_note "Enabled model download estimate is printed before downloads"
}

prepare_filebrowser_password() {
    local password="${FILEBROWSER_PASSWORD:-}"
    if [ -z "$password" ]; then
        FILEBROWSER_ADMIN_PASSWORD="$(random_password)"
        log "FILEBROWSER_PASSWORD was empty. Generated FileBrowser admin password: ${FILEBROWSER_ADMIN_PASSWORD}"
    elif [ "${#password}" -lt 12 ]; then
        FILEBROWSER_ADMIN_PASSWORD="$(random_password)"
        log "FILEBROWSER_AUTH was set but is shorter than 12 characters."
        log "Using generated FileBrowser password instead: ${FILEBROWSER_ADMIN_PASSWORD}"
    else
        FILEBROWSER_ADMIN_PASSWORD="$password"
        log "Using configured FileBrowser admin password."
    fi
    export FILEBROWSER_ADMIN_PASSWORD
}

setup_ssh() {
    mkdir -p ~/.ssh

    if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
        ssh-keygen -A -q
    fi

    if [[ -n "${PUBLIC_KEY:-}" ]]; then
        echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys
        chmod 700 -R ~/.ssh
    else
        RANDOM_PASS=$(openssl rand -base64 12)
        echo "root:${RANDOM_PASS}" | chpasswd
        log "Generated random SSH password for root: ${RANDOM_PASS}"
    fi

    grep -q '^PermitUserEnvironment yes' /etc/ssh/sshd_config || echo "PermitUserEnvironment yes" >> /etc/ssh/sshd_config
    /usr/sbin/sshd
}

export_runpod_env_vars() {
    log "Exporting RunPod/CUDA environment variables for SSH shells..."

    ENV_FILE="/etc/environment"
    PAM_ENV_FILE="/etc/security/pam_env.conf"
    SSH_ENV_FILE="/root/.ssh/environment"

    cp "$ENV_FILE" "${ENV_FILE}.bak" 2>/dev/null || true
    cp "$PAM_ENV_FILE" "${PAM_ENV_FILE}.bak" 2>/dev/null || true

    > "$ENV_FILE"
    > "$PAM_ENV_FILE"
    mkdir -p /root/.ssh
    > "$SSH_ENV_FILE"
    > /etc/rp_environment

    printenv | grep -E '^RUNPOD_|^PATH=|^CUDA|^LD_LIBRARY_PATH|^PYTHONPATH|^COMFYUI_DIR=|^ZINIGO_TEMPLATE_DIR=' | while read -r line; do
        name=$(echo "$line" | cut -d= -f1)
        value=$(echo "$line" | cut -d= -f2-)
        echo "$name=\"$value\"" >> "$ENV_FILE"
        echo "$name DEFAULT=\"$value\"" >> "$PAM_ENV_FILE"
        echo "$name=\"$value\"" >> "$SSH_ENV_FILE"
        echo "export $name=\"$value\"" >> /etc/rp_environment
    done

    grep -q 'source /etc/rp_environment' ~/.bashrc 2>/dev/null || echo 'source /etc/rp_environment' >> ~/.bashrc
    grep -q 'source /etc/rp_environment' /etc/bash.bashrc 2>/dev/null || echo 'source /etc/rp_environment' >> /etc/bash.bashrc

    chmod 644 "$ENV_FILE" "$PAM_ENV_FILE"
    chmod 600 "$SSH_ENV_FILE"
}

start_jupyter() {
    mkdir -p /workspace
    status_ok "JupyterLab starting on port 8888"
    log "Starting Jupyter Lab on port 8888..."
    nohup jupyter lab \
        --allow-root \
        --no-browser \
        --port=8888 \
        --ip=0.0.0.0 \
        --FileContentsManager.delete_to_trash=False \
        --FileContentsManager.preferred_dir=/workspace \
        --ServerApp.root_dir=/workspace \
        --ServerApp.terminado_settings='{"shell_command":["/bin/bash"]}' \
        --IdentityProvider.token="${JUPYTER_PASSWORD:-}" \
        --ServerApp.allow_origin='*' &> /jupyter.log &
    log "Jupyter Lab started."
}

setup_filebrowser() {
    mkdir -p /workspace/runpod-slim

    prepare_filebrowser_password
    local password="$FILEBROWSER_ADMIN_PASSWORD"

    if [ ! -f "$DB_FILE" ]; then
        log "Initializing FileBrowser database at $DB_FILE"
        filebrowser -d "$DB_FILE" config init
        filebrowser -d "$DB_FILE" config set --address 0.0.0.0
        filebrowser -d "$DB_FILE" config set --port 8080
        filebrowser -d "$DB_FILE" config set --root /workspace
        filebrowser -d "$DB_FILE" config set --auth.method=json
        filebrowser -d "$DB_FILE" users add admin "$password" --perm.admin
    else
        log "Using existing FileBrowser database at $DB_FILE"
        filebrowser -d "$DB_FILE" users update admin --password "$password" >/dev/null 2>&1 || \
            filebrowser -d "$DB_FILE" users add admin "$password" --perm.admin
    fi

    status_ok "FileBrowser starting on port 8080"
    log "Starting FileBrowser on port 8080..."
    nohup filebrowser -d "$DB_FILE" &> /filebrowser.log &
}

initialize_comfyui() {
    if [ -d "$OLD_VENV_DIR" ] && [ ! -d "$VENV_DIR" ]; then
        log "Detected old CUDA venv. Moving it aside before creating $VENV_DIR"
        mv "$OLD_VENV_DIR" "${OLD_VENV_DIR}.bak"
    fi

    if [ ! -d "$COMFYUI_DIR" ]; then
        log "First time setup: copying baked ComfyUI to workspace..."
        cp -r /opt/comfyui-baked "$COMFYUI_DIR"
        log "ComfyUI copied to $COMFYUI_DIR"
    fi

    if [ ! -d "$VENV_DIR" ]; then
        log "Creating ComfyUI venv at $VENV_DIR"
        cd "$COMFYUI_DIR"
        python3.12 -m venv --system-site-packages "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        python -m ensurepip
        python -m pip --version >/dev/null
        log "ComfyUI venv ready. Base packages are inherited from the image."
    else
        source "$VENV_DIR/bin/activate"
        log "Using existing ComfyUI installation and venv."
    fi
}

run_bootstrap() {
    if [ "${ZINIGO_SKIP_BOOTSTRAP:-false}" = "true" ]; then
        log "ZINIGO_SKIP_BOOTSTRAP=true; skipping template bootstrap."
        return
    fi

    section "3/7" "Custom Nodes"
    status_note "Bootstrap will ensure configured custom nodes"
    section "4/7" "Model Downloads"
    status_note "Bootstrap will print enabled downloads and disk estimate"
    section "5/7" "Workflow Validation"
    status_note "Bootstrap will validate bundled workflows"
    log "Running Zinigo ComfyUI template bootstrap..."
    python "$TEMPLATE_DIR/scripts/bootstrap.py" \
        --comfyui "$COMFYUI_DIR" \
        --template "$TEMPLATE_DIR" \
        --python "$VENV_DIR/bin/python" 2>&1 | tee -a "$SETUP_LOG"
}

start_comfyui() {
    cd "$COMFYUI_DIR"

    if [ ! -f "$ARGS_FILE" ]; then
        echo "# Add custom ComfyUI arguments here, one per line" > "$ARGS_FILE"
        log "Created ComfyUI args file at $ARGS_FILE"
    fi

    FIXED_ARGS="--listen 0.0.0.0 --port 8188 --enable-cors-header --enable-manager"

    if [ -n "${COMFYUI_ARGS:-}" ]; then
        FIXED_ARGS="$FIXED_ARGS $COMFYUI_ARGS"
    fi

    if [ -s "$ARGS_FILE" ]; then
        CUSTOM_ARGS=$(grep -v '^#' "$ARGS_FILE" | tr '\n' ' ')
        if [ -n "$CUSTOM_ARGS" ]; then
            FIXED_ARGS="$FIXED_ARGS $CUSTOM_ARGS"
        fi
    fi

    section "7/7" "ComfyUI"
    status_ok "ComfyUI starting on port 8188"
    log "Starting ComfyUI with args: $FIXED_ARGS"
    python main.py $FIXED_ARGS &
    COMFY_PID=$!
    trap "kill $COMFY_PID 2>/dev/null" SIGTERM SIGINT
    wait $COMFY_PID || true

    log "============================================="
    log "ComfyUI exited or crashed. SSH/Jupyter/FileBrowser are still available."
    log "Setup log: $SETUP_LOG"
    log "Manual restart: cd $COMFYUI_DIR && source $VENV_DIR/bin/activate && python main.py $FIXED_ARGS"
    log "============================================="
    sleep infinity
}

main() {
    mkdir -p /workspace/runpod-slim
    banner
    section "1/7" "Environment"
    normalize_runpod_env_aliases
    section "2/7" "Storage"
    log_storage_summary
    setup_ssh
    export_runpod_env_vars
    section "6/7" "Services"
    setup_filebrowser
    start_jupyter
    initialize_comfyui
    run_bootstrap
    start_comfyui
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
