variable "IMAGE" {
  default = "zinigofast/comfyui-runpod"
}

variable "TAG" {
  default = "dev-cuda12.8"
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
