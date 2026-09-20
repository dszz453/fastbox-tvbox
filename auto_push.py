"""
FastBox-TVBox -> Docker Hub 一键构建推送脚本

用法（二选一）：
  1) 先设置环境变量再运行：
       set DOCKERHUB_TOKEN=dckr_pat_xxxxxxxx
       python auto_push.py
  2) 直接运行，脚本会安全提示输入 Token（输入不回显）

安全说明：
  本脚本不保存任何密钥。请在 Docker Hub -> Account Settings -> Security
  生成 Access Token，用完可随时吊销。
"""

import getpass
import os
import subprocess
import sys

USERNAME = os.getenv("DOCKERHUB_USER", "zhangxiaonan1986")
IMAGE = f"{USERNAME}/fastbox-tvbox:latest"
ROOT = os.path.dirname(os.path.abspath(__file__))


def _fail(msg: str) -> None:
    print(f"[ERROR] {msg}")
    try:
        input("Press Enter to exit...")
    except EOFError:
        pass
    sys.exit(1)


def _read_token() -> str:
    token = (os.getenv("DOCKERHUB_TOKEN") or "").strip()
    if token:
        print("[OK] 已从环境变量 DOCKERHUB_TOKEN 读取凭据")
        return token
    try:
        token = getpass.getpass("请输入 Docker Hub Access Token (输入不回显): ").strip()
    except Exception:
        token = ""
    if not token:
        _fail("未提供 Docker Hub Token")
    return token


def main() -> None:
    print("=" * 60)
    print(" FastBox-TVBox -> Docker Hub Auto Pusher")
    print(f" Target Image: {IMAGE}")
    print("=" * 60)

    try:
        ver = subprocess.run(["docker", "--version"], capture_output=True, text=True)
    except Exception as e:
        _fail(f"无法执行 docker 命令: {e}")
    if ver.returncode != 0:
        _fail("Docker 未安装或未启动")
    print(f"[OK] Found {ver.stdout.strip()}")

    token = _read_token()

    print(f"\n[1/3] 登录 Docker Hub 账号 '{USERNAME}' ...")
    p_login = subprocess.Popen(
        ["docker", "login", "-u", USERNAME, "--password-stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = p_login.communicate(input=token)
    if p_login.returncode != 0:
        _fail(f"登录失败: {out} {err}")
    print("[SUCCESS] 登录成功")

    print(f"\n[2/3] 构建镜像: {IMAGE} ...")
    if subprocess.run(["docker", "build", "-t", IMAGE, "."], cwd=ROOT).returncode != 0:
        _fail("构建失败")
    print("[SUCCESS] 构建成功")

    print(f"\n[3/3] 推送到 Docker Hub: {IMAGE} ...")
    if subprocess.run(["docker", "push", IMAGE], cwd=ROOT).returncode != 0:
        _fail("推送失败")

    print("\n" + "=" * 60)
    print(" [CONGRATULATIONS] 已成功推送到 Docker Hub!")
    print(f" 地址: https://hub.docker.com/r/{USERNAME}/fastbox-tvbox")
    print("=" * 60)
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
