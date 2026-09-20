#!/bin/bash

echo "============================================================"
echo "     🚀 FastBox TVBox 智能聚合搜索与源服务 (Docker 版)      "
echo "============================================================"
echo ""

if ! command -v docker &> /dev/null; then
    echo "[错误] 未检测到 docker 命令，请先安装 Docker！"
    exit 1
fi

echo "[1/2] 正在构建并后台启动 FastBox 容器..."
if docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

if [ $? -eq 0 ]; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="<服务器IP>"
    fi
    echo ""
    echo "============================================================"
    echo "[成功] FastBox 容器已在后台运行！"
    echo "------------------------------------------------------------"
    echo "* Web 管理与搜索控制台: http://${LOCAL_IP}:8088"
    echo "* TVBox 豆瓣首页订阅:    http://${LOCAL_IP}:8088/tvbox?home=douban"
    echo "* TVBox 全能聚合订阅:    http://${LOCAL_IP}:8088/tvbox?home=full"
    echo "============================================================"
    echo ""
else
    echo "[错误] 启动失败，请检查 Docker 日志。"
fi
