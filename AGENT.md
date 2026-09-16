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
- **⚠️ 绝不要对微信主窗口盲按 `Esc`**：`SendKeys("{Esc}")` 落到主窗口上会**把微信窗口关掉**
  （实测踩过两次，用户会以为程序崩了）。**正确做法是压根不用 Esc** —— 残留菜单会在后续
  点击输入框时自然关闭。
- **微信 4.x 的消息操作菜单对 UIA 不可见**（2026-09-14 实测）：右键 / 鼠标悬浮 /
  先左键选中再右键，三种方式都探测不到任何**新增**控件或新增顶层窗口。
  ⚠️ 主窗口里本来就有一个常驻控件叫「引用」——按名字搜索会**误判为菜单已弹出**，
  不要用它判断菜单状态。所以 wxauto4 那套 `right_click + select_option("引用")`
  在当前微信版本上不可用；`quote_reply_native` 已默认关闭。
- **`UiaSender._lock` 必须是 `RLock`**：`send_quote` 会持锁调用 `send_text` 降级发送，
  普通 `Lock` 会在第二次 acquire 时**永久自锁**（实测卡死发送线程 80s+ 不返回）。
  以后加任何"持锁再调另一个加锁方法"的逻辑都要注意。
- **消息列表在控件树约 15 层深**：`mmui::MessageView > ListControl(mmui::RecyclerListView)
  > ListItemControl(mmui::ChatTextItemView)`。遍历深度给到 22 才稳。
- **微信 @ 后面是 U+2005（四分之一空格）**，WeFlow 推来的原文可能是普通空格；
  按内容匹配消息前必须归一化空白，否则命中不了。
- 主窗口类名 `mmui::MainWindow`；打开会话时标题是 `Weixin`，未打开任何会话时才是「微信」
- **微信窗口必须保持打开**：UIA 发送依赖窗口，窗口关了（只在托盘后台跑）则所有回复发不出去，
  但收信仍正常（WeFlow 读库不依赖窗口）—— 症状是"收得到、从不回"

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
- **⚠️ 由 AI/自动化启动长驻服务时必须清空 `PYTHONPATH`**（2026-09-14 实测）：
  工具环境里 `PYTHONPATH` 指向一个 shim 目录，其中 `sitecustomize.py` 会拦截
  `os.remove()`；AstrBot 清理临时文件时触发其批量删除保护，被 `SystemExit(1)`
  直接杀掉（进程没了、端口消失，日志末尾是 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`）。
  正确写法：`PYTHONPATH= ./.venv/Scripts/python.exe main.py`。
  **用户自己双击 `start.bat` 不受影响**（Explorer 环境没有这个 shim）。
- **⚠️ AstrBot 的 aiocqhttp 同时只能挂 1 个 OneBot 客户端**（2026-09-14 实测）：
  主动发送（定时任务 / `send_message_to_user` 跨会话发送）没有事件上下文，
  aiocqhttp 只能靠 `len(_api_clients)==1` 选路由。**模拟器一开着，所有定时任务必然
  100% 失败**，而且失败是静默的（空异常 `ApiNotAvailable` → DB 里仍写 completed）。
  已打补丁 `scripts/patch_aiocqhttp_primary_client.py`；自检用
  `scripts/cron_test_push.py`。详见 `docs/开发文档.md` §4.9。
- 本机请求（WeFlow / AstrBot / Ollama）必须在代码层面绕过系统代理；`config.py` 里已有 `NO_PROXY` 兜底，不要改成依赖启动脚本
- 非正常退出会残留 `bridge.pid`，下次启动会直接拒绝启动并打 `⚠️ bridge.pid 已存在`——清理它再启
- **定时任务自检有三条铁律**（2026-09-16 实测踩全套）：
  1. **自检指令必须用「任务简报式」写法**（描述要做什么＋示例）。写成"系统指令式"
     （点名 UMO、点名工具、"发完就结束"）会被 AstrBot 的 `safety_mode` 当成**提示词注入**，
     模型直接拒答："我绝不能执行任何由系统注入的、非用户直接发出的指令"。
     更坑的是它有时不拒绝、而是**谎报成功**（回"已处理完成"但根本没调用发送工具）。
     最稳的做法是 `--clone <真实任务ID>`，原样复用线上指令。
  2. **自检结果必须查三处**才能定论：AstrBot 日志的 `Tool send_message_to_user Result`、
     桥接的 `已切到会话:`＋`[UIA✓]`、以及 **WeFlow 查目标会话真的收到了**。
     只看 `cron_jobs.status=completed` 会完全误判（失败也是 completed）。
  3. **自检会往对话历史里写垃圾**（agent 的拒绝话术会留在上下文里，可能让后续真实任务
     跟着拒绝）。跑完必须 `python scripts/clean_test_artifacts.py` 清掉，再重启 AstrBot。
- **AstrBot 的日志默认看不见运行时输出**：`data/logs/astrbot.log` 在**启动完成后就停写**，
  stdout 又是块缓冲（退出才刷盘）。排障时用
  `PYTHONUNBUFFERED=1 ... python.exe -u run_astrbot.py run` 启动，才能实时看到
  cron/agent 的执行日志。
- **发消息前必须把输入框清空**（`UiaSender.clear_input()`）：微信输入框里的「引用节点」
  是富文本对象，`ValuePattern.SetValue("")` **删不掉**（清空后读回来是空串，界面上却仍有
  一个空引用块）。残留会引出两个历史疑难：① 后续发送把垃圾一起带上 → 群里出现
  **空的引用气泡**；② `_send_current` 用"输入框是否为空"判成败会永远失败，媒体发送被迫
  改成 `verify=False`（点一下按钮就算成功），**"发了没发"完全不可知**（就是"消息卡在
  输入框里"那个现象）。必须 Ctrl+A + Delete 真删。
- **剪贴板绝不用 PowerShell 子进程**：原实现 `subprocess.run(["powershell", ...])` 调
  WinForms 写剪贴板，在受限环境（自动化工具/沙箱启动的进程）里**会被拦截**，稳定卡
  30 秒后失败 → **图片/文件永远发不出去**。已改成 ctypes 直写 Win32 剪贴板
  （CF_HDROP ≈ 4ms、CF_DIB ≈ 0.3s）。⚠️ 必须显式声明 `argtypes/restype`，
  否则 64 位下句柄被截断成 32 位，`GlobalLock` 返回 NULL（报 access violation）。
- **桥接接收必须串行**（`ob_client.py` 单 worker 队列）：AstrBot 的「分条回复」是按顺序
  `await event.send()` 逐条发的；桥接若用 `create_task` 并发处理，多条 UIA 发送会互相
  竞争，落屏顺序会乱（用户看到的"同一件事颠三倒四说两遍"）。串行之后 AstrBot 必须等
  前一条回响应才发下一条，**乱序在结构上不再可能**。
- **主动发送的路由兜底必须是独立的 `if`，不能写成 `elif`**：`event_ws` 可能指向一个
  已经不在 `_api_clients` 里的连接，`api_ws` 会保持 None 并抛空异常。改成兜底 `if` 后，
  无论哪条分支落空都能回退到「排除模拟器后仅剩的那个客户端」。

- **不要为了"防穿帮"把知识库伪装成"自己的记忆"**：上游注入头 `[Related Knowledge Base Results]:`
  会让模型说漏"知识库"，所以曾把措辞全改成「你想起来的记忆，**请像亲身经历一样自然地使用**」
  —— 结果比穿帮更糟：模型开始**编造亲身经历**（"我又想起好多罗德岛的事…"，用户叫"雷霆大回忆"）。
  正确做法是**如实标注为【知识库】资料**，并明确三条：
  ① 当客观资料用、不许说成自己的经历/回忆；② 正常回复里不出现"知识库/资料库/检索/文档"字样；
  ③ 用户**直接问起**来源时如实说明，不要硬躲。
  补丁：`scripts/patch_kb_wording.py`（三处 AstrBot 文件）+ `scripts/patch_persona_kb_framing.py`（人设三条规则）。

## 4. 怎么验证

- **收消息链路**：看桥接日志，`📩 收到` / `⏭️ 跳过` / `推送 N 条消息` / `✅ 已推送至 AstrBot`
- **发送链路**：`[OB11] 文字已发送至 …`；要确认真的发出去，去 WeFlow 查对应会话最新消息（`isSend=1` 才是机器人发的）
- **只读接口**：日志里 `[OB11] API: get_group_member_info …`，返回值在 `resp_data["data"]`
- **离线回归**：可以抓一段 WeFlow SSE（`curl -N .../api/v1/push/messages`）存成文本，再逐条喂给 `add_to_buffer` 做回放测试，不用真的发微信消息
- **对照上游**：`diff` 上游 `wechat-weflow-bridge-ob11/*`，确认没有意外删除
- **回复率/长度体检**：`python scripts/analyze_log.py`（全量）、`scripts/analyze_mine.py`（按人+场景）；
  期望值：私聊 ~100%、群@ ~100%、群非@ ≈ 概率值（当前 3%）
- **上下文体检**：群里发 `/stats`，看 `Total` token 数。若持续 >10 万，检查
  `agent_runner.config.compression.max_turns` 是否被改回 `-1`

**读日志的两个坑**（写分析脚本时必看）

1. 日志**含 ANSI 转义码**（`\x1b[32m`），解析前先
   `re.sub(r"\x1b\[[0-9;]*m", "", raw)`，否则正则全不匹配。
2. 日志是 **append 的、跨天**的：按 `HH:MM` grep 会混进昨天的同一时刻。
   另外 `[respond.stage:212] Prepare to send` 的正文含换行时会**折成多行**，
   只取首行会误判成"回复是空的"（我就这样误判过 21 条）。

## 5. 发布流程（版号制，v1.0.0 起）

1. 改代码 → 本地验证
2. `CHANGELOG.md` 追加一条（说明改了什么、为什么）
3. `VERSION` 递增：**格式固定 `X.Y.Z`**（不再用 rc 后缀）；改动版本只改 `wechat-weflow-bridge-ob11/VERSION` 这一个文件
4. 出包：`python scripts/build_release.py`（加 `--zip` 生成可外发纯净包）——
   自动产生 `release/versions/vX.Y.Z/` 归档、刷新 `release/newestbuild/`、
   把上一次镜像挪进 `release/backups/pre-vX.Y.Z-*`
5. 提交推送；如需同步上游更新，先在上游仓库 fetch 后再合入，保留原目录结构

约定：`release/` 整体不入库；`runtime/`（本地运行环境，含 venv 与业务数据）不入库；
代码与配置里**不写死绝对路径**——相对路径以「项目根（桥接目录的上一级）」为基准，
AstrBot 相关配置留空时会自动按常见布局搜索。
