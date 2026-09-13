# AGENT.md — 给后续开发者 / AI 的维护约定

这份文档写给"接手改这个项目的人（或 AI）"。改代码前先读一遍，能省掉几个必踩的坑。

## 0. 这是什么

- 项目：`Akasha-WeChat_RC`，上游 [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 的 RC 分支
- 作用：把微信个人号接进 AstrBot。WeFlow 负责读消息（SSE），本桥接负责协议转换，AstrBot 负责 AI，发送靠 Windows UIA 操作微信窗口
- 代码目录：`wechat-weflow-bridge-ob11/`（**沿用上游路径，不要挪动**，否则与上游的 diff 会变成"全量移动"）
- 身份常量：`config.PROJECT_NAME` / `config.PROJECT_VERSION`（读同目录 `VERSION` 文件）

## 1. 模块职责

| 文件 | 职责 |
|---|---|
| `main.py` | 入口：启停、线程编排、Web 服务 |
| `bridge_core.py` | `WeFlowBridge`：SSE 消费、消息过滤、缓冲合并、构造事件、图片处理 |
| `ob_protocol.py` | OneBot 协议：构造事件、推送、处理 AstrBot 的 API 请求（含只读查询） |
| `ob_client.py` | 反向 WebSocket 客户端（连 AstrBot 的 aiocqhttp） |
| `senders.py` | 发送器工厂：`UiaSender` / `WeFlowApiSender`（后者**不可用**，见下） |
| `uia_sender.py` | UIA 自动化：找窗口、切联系人、找输入框、找发送按钮、发送 |
| `web_panel.py` | 内置 Web 面板（HTML/JS 内嵌） |
| `state.py` | 全局共享状态 + 各类缓存/映射 |
| `config.py` | 读 `config.json`，导出配置常量 |

## 2. 红线（改之前必须知道）

1. **不要删上游既有的代码**——包括未使用的导入、重复的类定义、看着像死代码的函数。用户明确要求保留，理由是与上游保持可 diff / 可合并。修 bug 可以，顺手清理不行。
2. **同一文件做多处编辑时必须串行**（一次一条）。并行下发编辑会静默丢改动（实测丢过 `import threading`、`from ctypes import wintypes`），而且工具会报"成功"。改完用 `diff` 对照上游确认。
3. **隐私红线**：任何要提交/公开的内容都不得含：Access Token、wxid / chatroom ID、真实人名与群名、内网 IP、含用户名的本机路径。提交前跑一遍 grep。`config.json`、`data/`、`*.log` 已在 `.gitignore` 里。
4. **长驻程序必须用可见控制台窗口启动**（用户要求）：双击 `start.bat`。不要以后台/隐藏窗口方式启动；确需临时后台时要先说明，并在之后切回。
5. **改完要留痕**：改功能 → `CHANGELOG.md` 加一条；涉及约定或坑 → 同步本文件；发版 → 更新 `VERSION`。

## 3. 已知坑

**UIA / 发送**
- 微信 4.x 的聊天输入框类名是 `mmui::ChatInputField`，在控件树**第 18 层左右**——遍历深度太小就找不到，会退化成用搜索框（现象：消息全被写进左上搜索框）
- 发送按钮是 `mmui::XOutlineButton`，名称「发送」，在输入框下方；左侧栏有无名图标按钮，按"无名"匹配会抓错
- `uiautomation` 2.x 移除了 `IsValuePatternAvailable` 和 `Control.SetValue`；要用 `GetPropertyValue(PropertyId.IsValuePatternAvailablePropertyId)` 和 `GetValuePattern().SetValue()`
- `SendKeys` 是发给**当前焦点控件**的，不是发给调用它的控件；发之前必须先 `SetFocus()`
- 判断是否真的发出去，唯一可靠判据是**输入框被清空**（发送按钮在空输入框时是禁用态，点了不报错）
- 主窗口类名 `mmui::MainWindow`；打开会话时标题是 `Weixin`，未打开任何会话时才是「微信」

**会话 / 身份**
- 微信 wxid 转数字 ID **不能**用内置 `hash()`：Python 对字符串 hash 每进程随机化，重启后同一联系人会变成新会话（面板出现重复会话）。现在用 MD5
- 群 ID 必须用 `xxx@chatroom`，不要用群名（群改名会产生新会话）
- SSE 推送的 `groupName` 会偶发缺失，必须走"持久化名称缓存"兜底，不能把原始 ID 当群名往外送

**消息 / 图片**
- 群图片门槛：只有与同一个人的 @ 属于同一次请求才读取，逻辑在 `bridge_core.add_to_buffer`；改这块时注意"图在 @ 前 / 在 @ 后"两条路径都要覆盖
- 图片理解两条路，`image_caption_model` 留空 = 原样交给 AstrBot，填了 = 桥接侧描述；**两条路都要保留**
- 只读 OneBot 接口里，群成员名单和群人数 WeFlow **取不到**（没有对应接口），`get_group_member_list` 只返回"发过言的成员"；注意 AstrBot 在拿不到人数时会用 `len(成员列表)` 兜底，所以这个数偏小——不要为了"看起来对"而编造
- 删除/替换任何过滤逻辑时，记得保留 `_log_skip()` 日志，否则被丢弃的消息会静默消失，排查时极难定位

**运行**
- 本机请求（WeFlow / AstrBot / Ollama）必须在代码层面绕过系统代理；`config.py` 里已有 `NO_PROXY` 兜底，不要改成依赖启动脚本
- 非正常退出会残留 `bridge.pid`，下次启动会直接拒绝启动并打 `⚠️ bridge.pid 已存在`——清理它再启

## 4. 怎么验证

- **收消息链路**：看桥接日志，`📩 收到` / `⏭️ 跳过` / `推送 N 条消息` / `✅ 已推送至 AstrBot`
- **发送链路**：`[OB11] 文字已发送至 …`；要确认真的发出去，去 WeFlow 查对应会话最新消息（`isSend=1` 才是机器人发的）
- **只读接口**：日志里 `[OB11] API: get_group_member_info …`，返回值在 `resp_data["data"]`
- **离线回归**：可以抓一段 WeFlow SSE（`curl -N .../api/v1/push/messages`）存成文本，再逐条喂给 `add_to_buffer` 做回放测试，不用真的发微信消息
- **对照上游**：`diff` 上游 `wechat-weflow-bridge-ob11/*`，确认没有意外删除

## 5. 发布流程

1. 改代码 → 本地验证
2. `CHANGELOG.md` 追加一条（说明改了什么、为什么）
3. `VERSION` 按 `上游版本-rc.N` 递增
4. 提交推送；如需同步上游更新，先在上游仓库 fetch 后再合入，保留原目录结构
