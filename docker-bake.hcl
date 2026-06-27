variable "IMAGE" {
  default = "zinigocreations/zinigo-comfyui-runpod-template"
}

variable "TAG" {
  default = "v0.1.1-cuda12.8"
}

group "default" {
  targets = ["cuda128"]
}

target "cuda128" {
  context = "."
  dockerfile = "Dockerfile"
  platforms = ["linux/amd64"]
  tags = ["${IMAGE}:${TAG}"]
}
