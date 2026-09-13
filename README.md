# Akasha-WeChat_RC

微信个人号 ↔ AstrBot 的桥接器（WeFlow + OneBot v11 / 反向 WebSocket）。
本仓库是 **[alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 的 RC（Release Candidate）分支**，在同一套架构上做稳定性与可维护性改进，目录结构沿用上游，方便对照 diff 与合并上游更新。

- **上游**：<https://github.com/alingalingling/Akasha-WeChat>
- **本分支仓库名**：`Akasha-WeChat_RC`
- **项目标识**：`PROJECT_NAME = "Akasha-WeChat_RC"`，版本号见 `wechat-weflow-bridge-ob11/VERSION`
- **许可证**：MIT（沿用上游，见 `wechat-weflow-bridge-ob11/LICENSE`）

> 名称中的 `_RC` 是长期固定的标识，改名目录或 fork 都不会影响它——日志首行会打印 `Akasha-WeChat_RC v<版本号>`，便于任何时候分辨运行的是哪一支。

---

## 架构

```
微信 ←→ WeFlow(5031) ──SSE──→ bridge ──WebSocket 客户端──→ AstrBot(aiocqhttp 11229)
                                  ↑                              │
                            main.py 启动                          │ API 回调
                            Web 面板 :8766  ←─────────────────────┘
                                  │
                        发送：UIA 操作微信窗口
```

- **读取**：WeFlow 解密本地消息库后 SSE 推送，不轮询、不依赖窗口渲染
- **大脑**：AstrBot（模型、人格、知识库、工具全部由它负责）
- **发送**：Windows UIA 自动化操作微信窗口（上游原方案）
- **面板**：内置 Web 控制面板，可在线改配置、启停、看日志

## 相对上游的改动

改动集中在"**能不能长期稳定跑**"，没有替换架构。完整开发日志见 [`CHANGELOG.md`](CHANGELOG.md)，给后续维护者/AI 的注意事项见 [`AGENT.md`](AGENT.md)。

**发送链路（UIA）**
- 控件遍历深度 14 → 26，并优先按类名 `ChatInputField` 精确定位聊天输入框（上游只找到搜索框，导致消息被写进搜索框）
- 显式排除搜索框；定位不到合适输入框时**直接中止**，不再退化为用搜索框
- 修复 `uiautomation 2.x` 移除的 API（`IsValuePatternAvailable` / `Control.SetValue`），改用 `GetPropertyValue` + `GetValuePattern()`
- 发送按钮定位修正：原先匹配到左侧栏无名图标，现按类名 `XOutlineButton` + 名称「发送」定位
- 发送结果以「输入框是否清空」为判据，依次尝试 发送按钮 → Enter → Ctrl+Enter，失败会在日志中明确报出
- 窗口句柄获取适配微信 4.x（`mmui::MainWindow`）与标题 `Weixin`
- 切联系人：先在左侧会话列表按名字点击（精确 > 前缀 > 包含），失败再退回 Ctrl+F 搜索；用标题栏校验是否真的切过去了，`switch_method` 可选 `auto`/`list`/`search`

**会话与身份**
- 会话 ID 从 `hash(wxid)` 改为 MD5：**上游的 hash 每个进程都会变**，桥接一重启同一联系人就变成新会话（面板里表现为"每个聊天出现两遍"），现已跨重启稳定
- 群 ID 用 `xxx@chatroom` 而不是群名，群改名不再产生新会话
- 持久化「微信 ID → 显示名」缓存（启动时从 WeFlow 全量预取 + 消息流增量回写），群名缺失时不再把 `xxx@chatroom` 当群名送出去

**消息与图片**
- 群图片门槛：只有与**同一个人的 @ 属于同一次请求**才读取（@ 前发的先暂存等 @，@ 后紧跟的直接读），避免群里任何人发图都触发
- 图片理解两条路：`image_caption_model` **留空** → 图片原样以 `base64://` 段交给 AstrBot（由它用主模型直看或走转述模型）；**填了** → 走上游的桥接侧描述（取图落盘 → 描述模型 → 发文字）
- 补全只读 OneBot 接口：`get_login_info` / `get_group_info` / `get_group_member_info` / `get_group_member_list` / `get_group_list` / `get_friend_list` / `get_stranger_info` / `get_msg`，AstrBot 现在能拿到真实群名与成员昵称
- 消息缓冲修复：推送期间到达的新消息会重新排期（上游会一直压在缓冲里）；自回复去重真正生效（上游只判断从不记录）

**可维护性**
- 本地请求（WeFlow / AstrBot / Ollama）在代码层面绕过系统代理，不依赖启动脚本设 `NO_PROXY`
- 被策略丢弃的消息会打日志（`⏭️ 跳过 …`，可按"会话+成员+原因"节流），不再静默消失
- 未使用导入/字段等**保持上游原样**，不做"顺手清理"
- `processed_ids` 加 FIFO 上限，避免长时间运行内存增长

## 前置条件

| 依赖 | 说明 |
|---|---|
| Windows | 需要桌面微信（发送靠 UIA，微信需可自动化） |
| Python 3.10+ | 运行桥接 |
| [WeFlow](https://weflow.top) | 已登录并开启 API 服务（默认 5031） |
| [AstrBot](https://github.com/AstrBotDevs/AstrBot) | 已部署，启用 **aiocqhttp** 适配器（反向 WS，端口如 11229） |

> WeFlow 只负责**读取**（它没有发送接口）。发送走 UIA，所以微信窗口需要能被自动化访问。

## 快速开始

```bash
cd wechat-weflow-bridge-ob11
pip install -r requirements.txt
```

首次运行会自动从 `config.example.json` 生成 `config.json`，然后填配置（也可以直接在 Web 面板改）：

| 关键项 | 说明 |
|---|---|
| `weflow_base_url` | WeFlow 地址，如 `http://127.0.0.1:5031` |
| `access_token` | WeFlow 的 Access Token |
| `astrbot_ob_url` | AstrBot 的 aiocqhttp 反向 WS 地址，如 `ws://127.0.0.1:11229/ws` |
| `bot_nicknames` | 机器人昵称（判定 @ 用） |
| `send_method` | 固定 `uia` |
| `group_reply_mode` | `mention`（仅 @ 回复，默认）/ `all` / `batch` |

启动：

```bash
python main.py          # 或双击 start.bat（会开一个可见的控制台窗口）
```

打开面板 <http://127.0.0.1:8766> 看运行状态与实时日志（`web_host` 默认 `0.0.0.0`，局域网可访问；只想要本机就改成 `127.0.0.1`）。

## 目录结构

```
Akasha-WeChat_RC/
├── README.md                 本文件（fork 说明）
├── AGENT.md                  给后续开发者 / AI 的约定与踩坑清单
├── CHANGELOG.md              开发日志（相对上游的改动史）
├── .gitignore
├── docs/
│   ├── upstream-SETUP.md     上游「从零开始搭建指南」
│   └── upstream-CLAUDE.md    上游给 AI 的模块速查
└── wechat-weflow-bridge-ob11/    ← 代码目录（沿用上游路径）
    ├── main.py bridge_core.py ob_protocol.py ob_client.py
    ├── senders.py uia_sender.py web_panel.py state.py config.py
    ├── config.example.json requirements.txt start.bat LICENSE
    ├── VERSION                版本号（长期标识的一部分）
    └── README.md              上游原始说明（保留未改）
```

## 版本与维护约定

- 版本号遵循 `上游版本-rc.N`（当前 `1.0.1-rc.1`），上游升级时同步前半段
- 每次改动都要在 `CHANGELOG.md` 留一条；改动涉及"约定/坑"时同步 `AGENT.md`
- **不删上游既有代码**（含未使用的导入、重复实现、看着像死代码的部分）——修 bug 可以，顺手清理不行，避免与上游合并时冲突

## 隐私提醒

- `config.json` 含 WeFlow Access Token，**已被 .gitignore 排除，切勿提交**
- 运行期 `data/chat_names.json` 会缓存真实会话名与 wxid，同样不入库
- 提 issue 或贴日志前，请先删掉 token、wxid、群名、内网 IP 与本机路径

## 致谢

上游 [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 以及 [AstrBot](https://github.com/AstrBotDevs/AstrBot)、[WeFlow](https://weflow.top)。
