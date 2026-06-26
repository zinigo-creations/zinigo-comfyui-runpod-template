FROM runpod/comfyui:cuda12.8

ENV ZINIGO_TEMPLATE_DIR=/opt/zinigo-comfyui-template
ENV COMFYUI_DIR=/workspace/runpod-slim/ComfyUI
ENV PYTHONUNBUFFERED=1

COPY config/ ${ZINIGO_TEMPLATE_DIR}/config/
COPY scripts/ ${ZINIGO_TEMPLATE_DIR}/scripts/
COPY workflows/ ${ZINIGO_TEMPLATE_DIR}/workflows/
COPY start.sh /start.sh

RUN chmod +x /start.sh ${ZINIGO_TEMPLATE_DIR}/scripts/*.py \
    && python3 -m py_compile ${ZINIGO_TEMPLATE_DIR}/scripts/*.py \
    && python3 ${ZINIGO_TEMPLATE_DIR}/scripts/validate_workflows.py \
        --workflows ${ZINIGO_TEMPLATE_DIR}/workflows \
        --custom-nodes ${ZINIGO_TEMPLATE_DIR}/config/custom-nodes.json \
    && if [ -d /opt/comfyui-baked ]; then \
        python3 ${ZINIGO_TEMPLATE_DIR}/scripts/install_custom_nodes.py \
            --comfyui /opt/comfyui-baked \
            --manifest ${ZINIGO_TEMPLATE_DIR}/config/custom-nodes.json \
            --python python3 \
            --install-deps ; \
       else \
        echo '/opt/comfyui-baked not found at build time; startup bootstrap will install nodes.' ; \
       fi

EXPOSE 8188 22 8888 8080

ENTRYPOINT ["/start.sh"]
