FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统基础依赖与时区
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
        curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（清华镜像源加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制应用代码与静态资源（含 pg.jar 离线爬虫套件）
COPY app/ ./app/
COPY static/ ./static/

# 运行时数据目录（存放网页端保存的配置）
RUN mkdir -p /app/data

# 暴露服务端口
EXPOSE 8088

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8088/health || exit 1

# 启动 FastAPI 异步服务
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "2"]
