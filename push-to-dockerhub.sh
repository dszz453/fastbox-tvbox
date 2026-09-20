#!/bin/bash

echo "============================================================"
echo "  🚀 FastBox Docker Hub 镜像一键构建与推送 (zhangxiaonan1986)"
echo "============================================================"
echo ""

DOCKER_USER="zhangxiaonan1986"
IMAGE_NAME="${DOCKER_USER}/fastbox-tvbox"
TAG="latest"

if ! command -v docker &> /dev/null; then
    echo "[错误] 未检测到 docker 命令，请先安装并启动 Docker！"
    exit 1
fi

echo "目标镜像: ${IMAGE_NAME}:${TAG}"
echo ""

echo "[1/3] 正在登录 Docker Hub (用户: ${DOCKER_USER})..."
docker login -u "${DOCKER_USER}"

if [ $? -ne 0 ]; then
    echo "[错误] 登录失败！"
    exit 1
fi

echo ""
echo "[2/3] 正在构建 Docker 镜像..."
docker build -t "${IMAGE_NAME}:${TAG}" .

if [ $? -ne 0 ]; then
    echo "[错误] 镜像构建失败！"
    exit 1
fi

echo ""
echo "[3/3] 正在推送镜像到 Docker Hub: ${IMAGE_NAME}:${TAG} ..."
docker push "${IMAGE_NAME}:${TAG}"

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "[成功] 镜像已成功发布到 Docker Hub！"
    echo "仓库地址: https://hub.docker.com/r/${IMAGE_NAME}"
    echo "运行命令:"
    echo "  docker run -d --name fastbox -p 8088:8088 --restart unless-stopped ${IMAGE_NAME}:${TAG}"
    echo "============================================================"
else
    echo "[错误] 推送失败，请检查网络与仓库权限。"
fi
