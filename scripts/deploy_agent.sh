#!/usr/bin/env bash
# Construye la imagen del agente (linux/arm64, Python 3.14), la sube a ECR y muestra el
# comando de Terraform que actualiza el Runtime. Requiere Docker y credenciales de AWS.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REPO_URL="$(terraform -chdir=infra output -raw agent_ecr_repository)"
TAG="$(git rev-parse --short=12 HEAD)"

if [ -n "$(git status --porcelain -- Dockerfile pyproject.toml uv.lock src)" ]; then
  echo "Hay cambios sin commitear en el agente: haz commit antes, la etiqueta es el hash de git." >&2
  exit 1
fi

aws ecr get-login-password --region "$REGION" |
  docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
docker buildx build --platform linux/arm64 --load -t "${REPO_URL}:${TAG}" .
docker push "${REPO_URL}:${TAG}"

echo
echo "Imagen subida: ${REPO_URL}:${TAG}"
echo "Actualiza el Runtime con: terraform -chdir=infra apply -var agent_image_tag=${TAG}"
