# Docker 部署与镜像发布指南（含虚拟机环境专项说明）

> 本文档针对 **Hyper-V 虚拟机环境**下 Docker Desktop 无法启动的问题，提供三种可落地的解决方案。

---

## 一、问题诊断结论

### 现象
Docker Desktop 安装完成后，启动时报错：
> **Virtualization support not detected（未检测到虚拟化支持）**

### 根本原因（来自 Docker Desktop 官方日志 `com.docker.backend.exe.log`）

```
engine linux/wsl failed to start: checking preconditions:
Virtual Machine Platform not enabled
No virtualization available

"hasNoVirtualization": true
"supportsVirtualization": false
```

### 逐层分析

| 检查项 | 实测结果 | 说明 |
| :--- | :--- | :--- |
| 运行环境 | Microsoft Hyper-V 网络适配器 | 本机是一台 **Hyper-V 虚拟机（Guest）** |
| CPU | AMD Ryzen 7 PRO 4750U | 支持虚拟化 |
| `HyperVisorPresent` | `True` | 已运行在虚拟机管理程序之上 |
| `SecondLevelAddressTranslationExtensions` | **`False`** | ⚠️ **关键**：宿主未向本虚拟机暴露 SLAT（二级地址转换） |
| Docker 后端 | `engine linux/wsl`（WSL2） | Docker Desktop 默认使用 WSL2 引擎 |
| WSL2 前置条件 | 未满足 | 需要「虚拟机平台」+ **嵌套虚拟化** |

**一句话总结**：
> Docker Desktop 的 WSL2 引擎需要「虚拟机平台」能力，而「虚拟机平台」又依赖 CPU 的嵌套虚拟化（Nested Virtualization）。
> 由于**宿主机没有为这台虚拟机开启嵌套虚拟化**，导致 Docker 引擎无法启动。

---

## 二、三种解决方案

### 🅐 方案 A：在宿主机开启嵌套虚拟化（本地 Docker 可用）

> **前提**：你有权限登录这台虚拟机所运行的**物理宿主机**（Windows Hyper-V 主机）。

#### 步骤 1：在**宿主机**上执行（需管理员 PowerShell）

```powershell
# 查看当前所有虚拟机名称
Get-VM | Select-Object Name, State

# 关闭目标虚拟机（必须是"关闭"，不能是"保存状态"）
Stop-VM -Name "<你的虚拟机名称>"

# 开启嵌套虚拟化（暴露 CPU 虚拟化扩展给虚拟机）
Set-VMProcessor -VMName "<你的虚拟机名称>" -ExposeVirtualizationExtensions $true

# 重新启动虚拟机
Start-VM -Name "<你的虚拟机名称>"
```

#### 步骤 2：回到**本虚拟机**内执行（需管理员 PowerShell）

```powershell
# 启用「虚拟机平台」与「Linux 子系统」组件
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# 重启本虚拟机
Restart-Computer
```

#### 步骤 3：重启后验证并启动 Docker

```powershell
# 验证虚拟化是否已就绪
Get-CimInstance Win32_Processor | Select-Object SecondLevelAddressTranslationExtensions
# 期望输出：True

# 启动 Docker Desktop，然后验证
docker version
```

✅ 成功标志：`docker version` 能同时输出 Client 和 Server 两部分信息。

完成后，直接双击项目根目录的 **`push-with-token.bat`** 即可自动构建并推送到 Docker Hub。

---

### 🅑 方案 B：使用 GitHub Actions 云端构建（**强烈推荐，无需本地 Docker**）

> **优势**：
> - ✅ 完全绕开本机虚拟化限制，不需要宿主机权限
> - ✅ 由 GitHub 云端服务器构建，不占用你本机 CPU / 内存 / 上传带宽
> - ✅ **自动构建 `linux/amd64` + `linux/arm64` 双架构镜像**（x86 服务器 + ARM 群晖/树莓派都能用）
> - ✅ 每次改代码推送后自动重新发布

项目内已内置完整工作流文件：`.github/workflows/docker-publish.yml`

#### 步骤 1：在 GitHub 网页创建空仓库

1. 打开 <https://github.com/new>
2. Repository name 填：`fastbox-tvbox`
3. **不要**勾选 "Add a README file"（保持空仓库）
4. 点击 **Create repository**

#### 步骤 2：配置 Docker Hub 密钥

1. 进入新仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`DOCKERHUB_TOKEN`
4. Secret 填：你的 Docker Hub Access Token（`dckr_pat_...` 那一串）
5. 点击 **Add secret**

#### 步骤 3：推送源码（一键脚本）

双击项目根目录的 **`push-source-to-github.bat`**，
按提示粘贴你的仓库地址即可，例如：
```
https://github.com/zhangxiaonan1986/fastbox-tvbox.git
```

#### 步骤 4：等待云端自动构建

1. 进入 GitHub 仓库 → **Actions** 标签页
2. 可以看到 `Build and Push FastBox Docker Image` 工作流正在运行
3. 约 3~5 分钟后变为 ✅ 绿色
4. 镜像已自动发布到：`https://hub.docker.com/r/zhangxiaonan1986/fastbox-tvbox`

---

### 🅒 方案 C：借用其他设备构建（有 NAS / 另一台电脑时）

如果家里有**群晖 / 极空间 / 威联通 NAS**，或另一台能正常运行 Docker 的电脑：

1. 把整个项目文件夹 `tvbox` 拷贝过去；
2. 在目标设备上执行：
   ```bash
   cd tvbox
   docker build -t zhangxiaonan1986/fastbox-tvbox:latest .
   docker login -u zhangxiaonan1986
   docker push zhangxiaonan1986/fastbox-tvbox:latest
   ```
   或直接双击 `push-with-token.bat`（Windows）/ 执行 `bash push-to-dockerhub.sh`（Linux）。

---

## 三、镜像发布成功后的使用方法

无论用哪种方案，只要镜像出现在 Docker Hub，就可以在任何设备上一键运行：

```bash
docker run -d \
  --name fastbox-tv \
  -p 8088:8088 \
  --restart unless-stopped \
  zhangxiaonan1986/fastbox-tvbox:latest
```

### TVBox 电视端配置

| 模式 | 配置地址 |
| :--- | :--- |
| 🌟 豆瓣热播首页（推荐） | `http://<设备IP>:8088/tvbox?home=douban` |
| ⚡ 极速纯搜版 | `http://<设备IP>:8088/tvbox?home=lite` |
| 📦 全能离线套件版 | `http://<设备IP>:8088/tvbox?home=full` |

---

## 四、方案对比速查表

| 对比项 | 🅐 宿主机开嵌套虚拟化 | 🅑 GitHub Actions | 🅒 其他设备构建 |
| :--- | :---: | :---: | :---: |
| 需要宿主机权限 | ✅ 需要 | ❌ 不需要 | ❌ 不需要 |
| 需要重启虚拟机 | ✅ 需要 | ❌ 不需要 | ❌ 不需要 |
| 双架构镜像 (amd64+arm64) | ❌ 仅本机架构 | ✅ 自动支持 | ❌ 仅本机架构 |
| 后续改代码自动发布 | ❌ 手动 | ✅ 自动 | ❌ 手动 |
| 推荐度 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 五、常见问题

**Q1：为什么我这台虚拟机明明能上网、能跑程序，却"没有虚拟化"？**
A：虚拟化能力和网络无关。普通程序直接使用 CPU 指令即可运行；但 Docker Desktop 需要再"套一层"轻量虚拟机（WSL2），这要求 CPU 的虚拟化扩展被**逐级透传**（宿主 → 虚拟机）。宿主机默认不透传，所以报"无虚拟化"。

**Q2：`SecondLevelAddressTranslationExtensions` 显示 False，是不是我的 CPU 太老？**
A：不是。Ryzen 7 PRO 4750U 完全支持 SLAT。显示 False 是因为**宿主机没有把它暴露给这台虚拟机**，属于配置问题而非硬件问题。

**Q3：我不想动宿主机，也不想用 GitHub，还有别的办法吗？**
A：可以试试把项目拷到 NAS 上构建（方案 C）。很多 NAS 自带 Docker 且不受此限制。

**Q4：GitHub Actions 构建需要付费吗？**
A：公开仓库（Public）完全免费且额度充足；私有仓库也有每月 2000 分钟免费额度，本项目单次构建约 3~5 分钟，完全够用。
