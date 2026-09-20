# FastBox - TVBox 智能极速聚合搜索与豆瓣热播订阅系统

FastBox 是一款专为 **TVBox / 影视仓 / 猫影视 / FongMi** 等大屏客户端设计的**全网多源极速聚合搜索与订阅服务系统**。支持一键 **Docker 部署**，支持以**豆瓣官方热播排行榜为 TVBox 首页**，兼具毫秒级全网并发搜索、切片秒播与网盘 4K 资源聚合、以及 PanCheck 链接探活防死链特性。

---

## 🌟 核心特性与设计亮点

### 1. 反应极快 (Extreme Speed)
- **多源异步并发**：采用 Python 异步高并发核心（`FastAPI` + `httpx` + `asyncio.gather`），搜索时并发探测全网 10+ 优质源。
- **毫秒级超时熔断**：设定全局 3 秒短超时熔断机制，即使个别冷门采集站或盘搜节点响应缓慢，也绝不阻塞整体返回，保障 TVBox 客户端秒出结果！
- **双层 TTL 智能缓存**：内置 LRU 内存高速缓存，热门关键词（如“抓娃娃”、“庆余年”）二次调阅 `< 10ms` 瞬间输出，大幅减少电视端转圈等待。

### 2. 资源极多 (Massive Resources)
- **全网网盘聚合搜 (借鉴 `dszz453/pansou-edge`)**：
  - 聚合夸克网盘、阿里云盘、百度网盘、迅雷云盘、UC网盘等多家云盘资源，轻松获取 4K/HDR/无删减原盘高码率资源。
- **高质量免网盘切片秒播源**：
  - 内置暴风、量子、红牛、光速、非凡、卧龙、极速等 7 大高速 CDN 直链切片采集站，老人小孩免登录、免配置 Token，点击即秒播，纯净无广告！
- **精选接口深度融合**：
  - 内置并静态托管 `pg.20260902-1029.zip` 中的 `pg.jar`、`lib/` 离线爬虫套件与各类稳定站源；
  - 融合《影视接口合集（五一特别版）》中验证过的长期稳定源。

### 3. PanCheck 死链秒检 (借鉴 `dszz453/PanCheck`)
- 针对网盘资源最大的痛点“链接失效/文件已被取消”，FastBox 内置轻量快速探活模块，对抓取出的网盘链接实施毫秒级并发探活，**自动过滤失效死链**，只把 100% 活链推送到 TVBox 前排！

### 4. 首页可选豆瓣首页 (Douban Home)
- **豆瓣热榜直达**：实时抓取豆瓣热门电影、热门电视剧（国产剧/美剧/日剧/韩剧/动漫）、热门综艺、Top250 排行榜；
- **自建海报防盗链反代**：内置 `/api/img` 极速图片代理，彻底解决 TVBox 加载豆瓣海报时出现的 `403 Forbidden` 破图问题；
- **点击卡片自动触发全网聚合**：在 TVBox 首页点击任意一部豆瓣高分影视，服务端自动在后台毫秒并发匹配全网所有可播放的切片直链与网盘线路，实现**“在豆瓣挑片，点开直接看”**！

---

## 🚀 Docker 一键部署

> ⚠️ **虚拟机用户请注意**：如果你在 **Hyper-V / VMware 虚拟机**中部署，且宿主未开启嵌套虚拟化，
> Docker Desktop 会报 `Virtualization support not detected`。
> 请先阅读 **[DEPLOY-GUIDE.md](./DEPLOY-GUIDE.md)**，其中提供了三种解决方案（含免本地 Docker 的云端构建方案）。

### 方式一：Docker Compose 一键启动 (推荐)

在项目目录下执行：

```bash
docker compose up -d
```

### 方式二：使用 Docker Hub 镜像直接运行 (最省事，免本地构建)

如果你或你的朋友在 NAS、软路由、云服务器上运行，无需复制代码，直接拉取运行：

```bash
docker run -d \
  --name fastbox-search \
  --restart unless-stopped \
  -p 8088:8088 \
  -v fastbox-data:/app/data \
  -e DEFAULT_HOME=douban \
  -e SEARCH_TIMEOUT=3.0 \
  zhangxiaonan1986/fastbox-tvbox:latest
```

> **务必保留 `-v fastbox-data:/app/data`**：网页里保存的配置（网盘密钥、pansou-edge 地址、
> PanCheck 地址、性能参数）都持久化在 `/app/data`。不挂载卷的话，容器重建后配置会丢失。

| 项目 | 值 |
|---|---|
| 镜像 | `zhangxiaonan1986/fastbox-tvbox:latest` |
| 架构 | `linux/amd64` / `linux/arm64`（自动匹配） |
| 基础镜像 | `python:3.11-slim` |
| 数据卷 | `/app/data`（网页配置持久化目录） |

### 方式三：一键推送到 Docker Hub (专属脚本)

在当前项目根目录下：
- **Windows**：直接双击 `push-to-dockerhub.bat`，即可全自动登录、构建并推送到 `zhangxiaonan1986/fastbox-tvbox:latest`；
- **Linux**：执行 `bash push-to-dockerhub.sh`。

> 脚本不会保存任何密钥。请先设置环境变量 `DOCKERHUB_TOKEN`，或运行 `python auto_push.py` 时按提示输入
> （输入不回显）。Token 在 Docker Hub → Account Settings → Security 生成，用完可随时吊销。

### 方式四：云端自动构建（无需本地 Docker，支持双架构）

仓库内置了 GitHub Actions 工作流 `.github/workflows/docker-publish.yml`：

- 推送到 `main` 分支、打 `v*.*.*` 标签、或在 Actions 页面手动 `Run workflow` 都会触发；
- 自动构建 `linux/amd64` + `linux/arm64` 双架构并发布到 Docker Hub；
- 前置条件：在仓库 **Settings → Secrets and variables → Actions** 中添加 `DOCKERHUB_TOKEN`。

这是**虚拟机用户**（宿主未开嵌套虚拟化、本地 Docker 无法启动）的推荐方案，详见 [DEPLOY-GUIDE.md](./DEPLOY-GUIDE.md)。

启动完成后，打开浏览器访问：`http://<你的服务器IP>:8088` 即可进入现代化 Web 管理与搜索控制台！

---

## 📺 TVBox / 影视仓 使用配置教程

### 1. 获取订阅链接

打开 FastBox 的 Web 控制台页面（`http://<服务器IP>:8088`），系统会自动根据你的访问网络识别出正确的配置链接。

| 首页模式 | 订阅配置 URL | 说明 |
| :--- | :--- | :--- |
| **🌟 豆瓣热播首页 (推荐)** | `http://<服务器IP>:8088/tvbox?home=douban` | 首页呈现豆瓣热门电影电视排行榜，点击自动全网找片播放 |
| **⚡ 极速秒播纯搜版** | `http://<服务器IP>:8088/tvbox?home=lite` | 极致精简，仅包含豆瓣热播分类与聚合搜索源 |
| **📦 PG 全能离线套件版** | `http://<服务器IP>:8088/tvbox?home=full` | 完整挂载本地 pg.jar 离线爬虫包与上百个影视站点 |

### 2. 在 TVBox 客户端中填入

1. 打开电视上的 **TVBox / 影视仓 / 猫影视 / FongMi** 等应用；
2. 遥控器进入 **设置 ➔ 配置地址 (或接口地址)**；
3. **输入法输入**：填入上述表格中的配置链接；
4. **扫码极速填入**：在手机上打开 FastBox 控制台页面，手机微信/浏览器直接扫描右侧的“二维码”，一键将地址推送到电视客户端上，免去遥控器输入的烦恼！

---

## ⚙️ 配置指南（网页可视化 + 扫码授权）

FastBox 的配置分为两大类，**全部无需改代码、无需重启容器**：

| 配置类别 | 配置方式 | 入口 |
| :--- | :--- | :--- |
| **网盘密钥** | 📱 **扫码授权**（阿里云盘）/ 扫码填写（其他网盘） | 网页 → 「🔑 网盘密钥」 |
| **pansou-edge 地址** | 🌐 网页表单 + 一键连通性测试 | 网页 → 「⚙️ 系统设置」 |
| **PanCheck 地址** | 🌐 网页表单 + 一键连通性测试 | 网页 → 「⚙️ 系统设置」 |
| **性能 / 首页 / 缓存** | 🌐 网页表单 | 网页 → 「⚙️ 系统设置」 |

> 💡 网页端保存的配置写入 `data/runtime_config.json`，**优先级高于环境变量**，且挂载了 `./data` 卷后重启容器依然保留。

### 1️⃣ 网盘密钥（扫码授权）

进入网页顶部 **「🔑 网盘密钥」** 标签页：

#### 阿里云盘 — 真正的扫码授权登录

1. 点击 **「📱 扫码授权登录」**；
2. 弹出二维码，用手机 **阿里云盘 App** 扫描；
3. 手机上点击「确认登录」；
4. 系统自动获取 `refresh_token`，并调用兑换接口拿到 `open_token`，**自动写入配置**。

> 全程无需手动复制任何 Cookie，是目前最省心的方式。若扫码流程因官方接口调整而失效，可改用「手动填写 open_token」。

#### 夸克 / UC / 115 网盘 — 手机扫码填写

1. 点击 **「📱 手机扫码填写」**；
2. 用手机相机 / 微信扫描弹出的二维码；
3. 手机会打开一个填写页，在手机上粘贴 Cookie 后点保存；
4. 配置立即写入服务器。

> 相比在电视遥控器上一个字一个字敲，扫码后在手机上粘贴体验好得多。

#### 迅雷 / PikPak — 账号密码

直接在网页表单填写账号密码即可。

### 2️⃣ pansou-edge 网盘聚合搜索（可选但推荐）

> **什么是 pansou-edge？** 它是基于 Cloudflare Workers 的自建网盘搜索聚合服务（参考 [dszz453/pansou-edge](https://github.com/dszz453/pansou-edge)）。
> 自建后搜索速度更快、无频率限制、结果更稳定。

**在网页「⚙️ 系统设置」中配置：**

| 字段 | 说明 | 示例 |
| :--- | :--- | :--- |
| **pansou-edge 服务地址** | 你部署好的 Worker 地址（结尾不要带 `/`） | `https://pansou.yourdomain.workers.dev` |
| **访问鉴权 Token** | 若 Worker 里配了 `AUTH_TOKEN` 则填写 | `your_secret_token` |
| **启用网盘聚合搜索** | 勾选后生效 | ✅ |

填写后点击 **「🔌 测试连接」**，系统会自动探测 `/api/search`、`/search`、`/health` 等多个常见端点并给出结果。

**留空时的行为**：自动回退使用内置的公开盘搜节点，功能不受影响。

**也可用环境变量配置**（docker-compose.yml）：
```yaml
environment:
  - PANSOU_EDGE_URL=https://pansou.yourdomain.workers.dev
  - PANSOU_EDGE_TOKEN=your_secret_token
```

### 3️⃣ PanCheck 网盘死链检测（可选）

> **什么是 PanCheck？** 多平台网盘分享链接有效性检测系统（参考 [Lampon/PanCheck](https://github.com/Lampon/PanCheck)），默认监听 `8774` 端口。

**在网页「⚙️ 系统设置」中配置：**

| 字段 | 说明 | 示例 |
| :--- | :--- | :--- |
| **PanCheck 服务地址** | 自建 PanCheck 的地址 | `http://192.168.1.10:8774` |
| **检测模式** | `auto` / `remote` / `local` / `off` | `auto` |

**四种检测模式说明：**

| 模式 | 行为 | 适用场景 |
| :--- | :--- | :--- |
| `auto` | 配了地址走远程，否则用内置 | **默认推荐** |
| `remote` | 强制使用远程 PanCheck 服务 | 已部署 PanCheck，追求最准 |
| `local` | 强制使用内置轻量探活（HTTP 关键字判断） | 不想部署额外服务 |
| `off` | 完全关闭检测（最快） | 追求极致速度 |

填写后点击 **「🔌 测试连接」** 即可验证。

**也可用环境变量配置**：
```yaml
environment:
  - PANCHECK_MODE=auto
  - PANCHECK_URL=http://192.168.1.10:8774
```

### 4️⃣ 性能参数调优

网页「⚙️ 系统设置 → 性能与体验」中可实时调整：

| 参数 | 默认 | 说明 |
| :--- | :--- | :--- |
| **默认首页模式** | `douban` | 新订阅链接默认使用的首页 |
| **搜索超时熔断（秒）** | `3.0` | 越小越快；推荐 2.5~3.5 |
| **最大并发数** | `20` | 同时进行的搜索请求上限 |
| **搜索缓存有效期（秒）** | `1800` | 相同关键词在此期内直接命中缓存 |
| **豆瓣数据缓存有效期（秒）** | `7200` | 豆瓣榜单缓存时长 |
| **海报防盗链代理** | 开 | 解决电视端豆瓣海报 403 破图 |
| **弹幕** | 开 | 是否启用弹幕 |

> 📊 **实测性能**：首次搜索约 **1.5~1.9 秒**，缓存命中约 **0.02 毫秒**（比修复前提速约 9 倍）。

### 5️⃣ 配置自检接口

浏览器直接访问 `/api/config/status`，可查看当前所有配置的生效状态（不含密钥明文）：

```bash
curl http://<服务器IP>:8088/api/config/status
```

返回内容包括：pansou-edge 是否启用及地址、PanCheck 检测模式与实际生效方式、各网盘密钥是否已配置等。

---


## 🛠️ API 接口一览表

FastBox 同时遵循标准 MacCMS V10 (VOD) 协议，可直接作为一个独立的“采集站/聚合搜索站点”接入到你现有的任何 TVBox 接口配置中：

- **TVBox 订阅主接口**：`GET /tvbox` 或 `GET /sub`
  - 参数：`home=douban` (豆瓣首页) | `home=lite` (轻量纯搜) | `home=full` (全量)
- **MacCMS V10 VOD 标准接口**：`GET /api/vod`
  - 搜索影片：`GET /api/vod?ac=detail&wd=抓娃娃`
  - 查看详情：`GET /api/vod?ac=detail&ids=douban_123_抓娃娃`
  - 分类浏览：`GET /api/vod?ac=detail&t=hot_movie&pg=1`
- **豆瓣分类列表**：`GET /api/douban/categories`
- **豆瓣数据获取**：`GET /api/douban/list?type_id=hot_tv&page=1`
- **图片防盗链代理**：`GET /api/img?url=https://img1.doubanio.com/...`
- **Web 统一搜索接口**：`GET /api/search?q=庆余年`
- **清理内存缓存**：`POST /api/cache/clear?kind=all|search|douban|pancheck`
  - 排查「某关键词结果不完整」时一键重聚合，无需重启容器

### 配置与扫码授权接口

- **配置自检面板**：`GET /api/config/status`
- **读取全部可配置项**：`GET /api/settings`
- **保存配置**：`POST /api/settings` （Body: `{"settings":{...}}`）
- **恢复默认**：`POST /api/settings/reset`
- **测试 pansou-edge 连通性**：`POST /api/settings/test/pansou?url=...`
- **测试 PanCheck 连通性**：`POST /api/settings/test/pancheck?url=...`
- **网盘密钥读取（脱敏）**：`GET /api/token`
- **网盘密钥保存**：`POST /api/token`
- **阿里云盘扫码—生成二维码**：`POST /api/qr/aliyun/generate`（返回 `sid` 与 `state`）
- **阿里云盘扫码—轮询状态**：`GET /api/qr/aliyun/poll?sid=...&state=...`
  （`state` 必须原样回传，用于在多 worker 部署下跨进程还原会话）
- **阿里云盘扫码—保存凭证**：`POST /api/qr/aliyun/save`
- **其他网盘手机填写页**：`GET /api/qr/mobile/{quark|uc|115|thunder|pikpak}`

> ⚠️ 调用方注意：`/api/qr/aliyun/poll` 的 `state` 参数不可省略。
> 省略后若请求被负载均衡到另一个 worker 进程，会返回 `NOTFOUND`（旧版本返回 `EXPIRED`），
> 导致「扫码成功却保存不了」。


---

## 📁 目录结构

```
.
├── Dockerfile                  # Docker 构建清单 (Python 3.11-slim)
├── docker-compose.yml          # Docker Compose 编排文件
├── requirements.txt            # Python 依赖库
├── README.md                   # 详细使用与说明文档
├── DEPLOY-GUIDE.md             # 部署指南（含虚拟机环境专项方案）
├── app/
│   ├── main.py                 # FastAPI 核心入口与服务装配
│   ├── config.py               # 配置层（网页配置 > 环境变量 > 默认值）
│   ├── core/
│   │   ├── aggregator.py       # 极速多源并发聚合引擎（全局截止熔断）
│   │   ├── douban.py           # 豆瓣热榜分类与海报转换器
│   │   ├── pan_check.py        # PanCheck 网盘死链探活（远程/内置双模式）
│   │   ├── aliyun_qr.py        # 阿里云盘扫码授权登录
│   │   ├── runtime_config.py   # 运行时可变配置持久化存储
│   │   └── cache.py            # 高性能 TTL 内存缓存
│   ├── providers/
│   │   ├── base.py             # 搜索源抽象基类
│   │   ├── collectors.py       # 7大免网盘高清切片秒播采集站源
│   │   └── pansou.py           # 网盘聚合搜索（支持自建 pansou-edge）
│   ├── routers/
│   │   ├── tvbox.py            # TVBox 订阅生成路由
│   │   ├── vod.py              # 标准 MacCMS V10 协议路由
│   │   ├── douban_api.py       # 豆瓣分类与防盗链图片代理路由
│   │   ├── search.py           # Web 控制台搜索 API
│   │   ├── token_api.py        # 网盘密钥管理与配置自检
│   │   └── config_api.py       # 系统设置、连通性测试、扫码授权
│   └── templates/
│       └── index.html          # Web 控制台（搜索/密钥/设置 三标签页）
├── data/
│   └── runtime_config.json     # 网页端保存的配置（需挂载持久化）
└── static/
    └── pg/                     # 本地托管的 pg.jar 与爬虫/配置文件 (来自 pg.zip)
```

---

## 💡 常见问题 FAQ

**Q1：TVBox 上打开豆瓣首页，海报加载很慢或者偶尔破图怎么办？**  
A：无需担心！FastBox 内部所有豆瓣海报均自动通过服务端的 `/api/img` 代理加速分发，并附带防盗链伪装头与内存图片缓存，电视端加载流畅且 100% 不破图。

**Q2：如何调整搜索超时时间？**  
A：**推荐直接在网页上改** —— 打开 `http://<IP>:8088` → 「⚙️ 系统设置」→「性能与体验」→ 修改「搜索超时熔断」，保存后**立即生效**，无需重启容器。也可在 `docker-compose.yml` 中设置 `SEARCH_TIMEOUT=2.5`（作为默认值）。

**Q3：我想把它部署在内网穿透（如 FRP / Cloudflare Tunnel / DDNS）后，TVBox 怎么用？**  
A：FastBox 采用动态 Host 解析设计，只要你通过 `http://your-domain.com:8088` 访问控制台，复制出的链接自动就是你的域名地址，TVBox 在外网也能完美拉取配置和进行极速搜索！

**Q4：网盘密钥一定要配置吗？**  
A：**不需要**。不配置任何网盘密钥，依然可以正常使用 7 大免网盘切片秒播源（暴风、量子、红牛等），点开即播。配置网盘密钥只是为了额外解锁「网盘 4K 原盘」这类高码率资源。

**Q5：阿里云盘扫码提示「二维码已过期」/ 扫码后保存不了怎么办？**  
A：二维码有效期约 5 分钟，过期后点击弹窗里的「刷新二维码」重新生成即可。

> **v1.1 已修复**：早期版本把扫码会话存在单个进程内存中，而服务以 `--workers 2` 多进程运行，
> 轮询请求一旦落到另一个 worker 就会误报「二维码已过期」并停止轮询（实测 20 次轮询中 8 次误报）。
> 现已改为**无状态会话**：生成二维码时下发 `state`，轮询时原样回传即可跨进程还原，
> 并新增「连续 3 次异常才判定过期」的容错。如果你仍遇到该问题，请确认镜像已更新到最新版。

若扫码接口因官方调整持续失败，可改用「手动填写 open_token」。

**Q6：网页上改的配置，重启容器后会丢吗？**  
A：不会。配置写入 `data/runtime_config.json`。只要 `docker-compose.yml` 中保留了 `- ./data:/app/data` 这行卷挂载，重启后配置依然生效。

**Q6-1：扫码保存的网盘凭证，容器重建后会丢吗？**  
A：**不会（v1.1 起）**。凭证会同时写入两处：

| 位置 | 作用 |
| --- | --- |
| `/app/static/pg/lib/tokenm.json` | pg.jar 实际读取的主文件 |
| `/app/data/tokenm.json` | 数据卷内的持久化镜像 |

容器启动时会自动从数据卷还原主文件，因此 `docker compose up -d --force-recreate`、
重新拉取镜像等操作都不会丢失扫码结果（前提仍是挂载了 `- ./data:/app/data`）。

**Q7：`auto` / `remote` / `local` / `off` 四种 PanCheck 模式怎么选？**  
A：一般保持 `auto` 即可（配了地址就走远程，没配就用内置）。如果你追求极致速度、不在乎少量死链，选 `off`；如果已部署 PanCheck 且要求最准，选 `remote`。

**Q8：怎么确认我的 pansou-edge / PanCheck 地址配对了？**  
A：在「⚙️ 系统设置」中填好地址后，点击旁边的 **「🔌 测试连接」** 按钮，系统会自动探测多个常见端点并返回 HTTP 状态码，一目了然。也可访问 `/api/config/status` 查看全局配置自检结果。

