IMAGE ?= zinigocreations/zinigo-comfyui-runpod-template
TAG ?= v0.1.3-cuda12.8

.PHONY: validate build run shell zip

validate:
	python3 -m py_compile scripts/*.py
	python3 scripts/validate_workflows.py --workflows workflows --custom-nodes config/custom-nodes.json
	python3 scripts/download_models.py --comfyui . --manifest config/models.json --dry-run || true

build:
	docker build -t $(IMAGE):$(TAG) .

run:
	docker run --gpus all --rm -it \
		-p 8188:8188 -p 8080:8080 -p 8888:8888 -p 2222:22 \
		--env-file runpod-env.example \
		-v comfy-workspace:/workspace \
		$(IMAGE):$(TAG)

shell:
	docker run --rm -it --entrypoint /bin/bash $(IMAGE):$(TAG)

zip:
	cd .. && zip -r zinigo-comfyui-runpod-template.zip zinigo-comfyui-runpod-template
