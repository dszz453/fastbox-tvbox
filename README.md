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
  -e DEFAULT_HOME=douban \
  -e SEARCH_TIMEOUT=3.0 \
  zhangxiaonan1986/fastbox-tvbox:latest
```

### 方式三：一键推送到 Docker Hub (专属脚本)

在当前项目根目录下：
- **Windows**：直接双击 `push-to-dockerhub.bat`，即可全自动登录、构建并推送到 `zhangxiaonan1986/fastbox-tvbox:latest`；
- **Linux**：执行 `bash push-to-dockerhub.sh`。

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

---

## 📁 目录结构

```
.
├── Dockerfile                  # Docker 构建清单 (Python 3.11-slim)
├── docker-compose.yml          # Docker Compose 编排文件
├── requirements.txt            # Python 依赖库
├── README.md                   # 详细使用与说明文档
├── app/
│   ├── main.py                 # FastAPI 核心入口与服务装配
│   ├── config.py               # 系统环境与超参数配置
│   ├── core/
│   │   ├── aggregator.py       # 极速多源并发聚合并发引擎
│   │   ├── douban.py           # 豆瓣热榜分类与海报转换器
│   │   ├── pan_check.py        # PanCheck 网盘死链探活检测
│   │   └── cache.py            # 高性能双层 TTL 内存缓存
│   ├── providers/
│   │   ├── base.py             # 搜索源抽象基类
│   │   ├── collectors.py       # 7大免网盘高清切片秒播采集站源
│   │   └── pansou.py           # 夸克/阿里/百度全网盘搜聚合源
│   ├── routers/
│   │   ├── tvbox.py            # TVBox 订阅生成路由
│   │   ├── vod.py              # 标准 MacCMS V10 协议路由
│   │   ├── douban_api.py       # 豆瓣分类与防盗链图片代理路由
│   │   └── search.py           # Web 控制台搜索 API
│   └── templates/
│       └── index.html          # 现代化交互式 Web 控制台与二维码生成
└── static/
    └── pg/                     # 本地托管的 pg.jar 与爬虫/配置文件 (来自 pg.zip)
```

---

## 💡 常见问题 FAQ

**Q1：TVBox 上打开豆瓣首页，海报加载很慢或者偶尔破图怎么办？**  
A：无需担心！FastBox 内部所有豆瓣海报均自动通过服务端的 `/api/img` 代理加速分发，并附带防盗链伪装头与内存图片缓存，电视端加载流畅且 100% 不破图。

**Q2：如何调整搜索超时时间？**  
A：在 `docker-compose.yml` 中修改 `SEARCH_TIMEOUT=2.5`（单位秒）。数值越小响应越快；数值稍大（如 3.5~4.0）能包含更多更远的网盘源，推荐设置为 3.0 秒。

**Q3：我想把它部署在内网穿透（如 FRP / Cloudflare Tunnel / DDNS）后，TVBox 怎么用？**  
A：FastBox 采用动态 Host 解析设计，只要你通过 `http://your-domain.com:8088` 访问控制台，复制出的链接自动就是你的域名地址，TVBox 在外网也能完美拉取配置和进行极速搜索！
