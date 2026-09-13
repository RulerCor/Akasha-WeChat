# 开发日志

本文件记录 `Akasha-WeChat_RC` 相对上游 [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 的改动。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)：`新增` / `修复` / `变更` / `其他`。
约定见 [`AGENT.md`](AGENT.md)——尤其**不得删除上游既有代码**，本分支只做修复与增量。

## [1.1.0]

这一版的主题：**主动回复黑名单 + 文件发送**。

### 新增

- **主动回复黑名单**（AstrBot 核心补丁）：`provider_ltm_settings.active_reply.blacklist`，
  与白名单并行、优先级更高——黑名单里的群（群 ID 或 UMO）绝不随机插话，不影响 @ 唤醒回复。
  AstrBot WebUI 的配置 schema 已同步扩展，面板可直接编辑；
  桥接面板「成员与权限」页同步增加黑名单群勾选框 + 自定义条目。
- **文件发送**（桥接）：OneBot `file` 段不再被静默忽略。支持 `file:///` URI、
  本地路径、`base64://`、http(s) 下载四种来源；发送走 UIA 剪贴板
  CF_HDROP 文件拖放格式（SetFileDropList → Ctrl+V → Enter），任意类型文件均可。

### 修复

- 之前 bot 生成文件后"发不出去"且桥接静默回 ok——现在文件段会真正投递，
  失败时日志明确记录 `[UIA✗] 文件`。

## [1.0.0]

**版号制的起点**（此前为 `1.0.1-rc.1 ~ rc.7` 预发布序列，全部归档在下方）。
从这一版起：版本号只用 `vX.Y.Z`，用 `scripts/build_release.py` 出包，
产物落在 `release/versions/vX.Y.Z/` 归档 + `release/newestbuild/` 最新镜像
（约定对齐 `C:\WechatBotShare`）。

### 变更

- **目录整合**：桥接运行环境与 AstrBot 一并迁入项目根 `runtime/`（bridge / astrbot），
  仓库、模拟器、文档、发布产物同处一个根目录，整目录可搬迁。
- **路径全部相对化**：配置里的 `astrbot_config_file`、`astrbot_attachments` 改为相对路径，
  以「项目根（桥接目录的上一级）」为基准；留空时按常见布局自动搜索
  （runtime/astrbot、同级 AstrBot…）。**拷到任何电脑、任何盘符、任何目录都能直接跑**。
- **发布流程脚本化**：`scripts/build_release.py` 读取 `VERSION`，自动生成版本归档、
  刷新 newestbuild、回滚备份（backups/pre-vX.Y.Z-*）与可选纯净 zip。

### 继承的历史改动（rc.1 ~ rc.7 一览）

- rc.2 群聊内置指令透传（`/sid` 等不再被"某某在群某某中说："外壳顶掉）
- rc.3 管理员/白名单可视化；同人同 ID（`user_id=md5(wxid)`，加一次全局生效）
- rc.4 群指令需 @ 触发、每群回复开关、白名单可视化、设置页重组
- rc.5 面板分工修正（图片理解交还 AstrBot；随机插话文案对齐）
- rc.6 修复 all 模式逐条必回（非 @ 消息不再被硬塞 At 段）
- rc.7 合并 mention/all 为「标准模式」

## [1.0.1-rc.7]

这一版的主题：**合并 mention / all两种普通模式**。

### 变更

- **「仅@回复」与「全部回复」合并为「标准模式」**：rc.6 修复 @ 段之后，两种普通模式在桥接侧的
  区别只剩「非 @ 消息要不要转发」——转发过去 AstrBot 也只是按随机插话（active_reply）掷骰，
  关掉就等于「仅@回复」。桥接不再需要第二个普通模式：
  - 面板选项由 3 个减为 2 个：**标准模式 / 批处理**；
  - 旧配置值 `mention` 在读取与运行时自动归一化为 `all`，无需改配置文件；
  - 上游 mention 相关代码保留不删（归一化后不可达），符合不删上游代码的约定。
- 「随机插话」的生效前提说明同步更新（不再要求切换 all，批处理除外）。

## [1.0.1-rc.6]

这一版的主题：**修复 all 模式逐条必回**。

### 修复

- **all 模式下每条群消息都被 AstrBot 当成 @ 唤醒**：推送事件里的 `@机器人` 段是无条件加的，
  `mention` 模式下只有 @ 过的消息能走到推送这一步所以从未暴露；切到 `all` 后所有非 @ 消息
  也被硬塞 `[At:]`，AstrBot 视为唤醒逐条回复，`active_reply` 随机插话机制完全失效。
  现在 @ 段只在**这批消息里真的有人 @ 过机器人**时才加（按批次记录、推送后复位，不跨批继承）。
- **all / batch 模式下裸斜杠指令未拦截**：「指令必须 @ 才触发」此前只挂在 mention 门槛上，
  现已独立成模式无关的拦截规则；@ 后仍无外壳透传。

## [1.0.1-rc.5]

这一版的主题：**明确面板分工，消除与 AstrBot WebUI 的重复感**。

### 变更

- **设置页分工修正**：桥接面板只保留微信侧管道配置（连接 / 机器人身份 / 消息 / 图片管道参数 / 高级）。
  「怎么理解图片」交还 AstrBot 面板（主模型多模态或其图片转述模型）；上游遗留的「桥接侧图片转述」
  降级到页尾独立分组并标注「默认关闭 · 一般不用改」，功能保留不删除。
- **主动回复文案对齐 AstrBot**：面板改用「随机插话」措辞并明确——这就是 AstrBot 配置里
  「随机小概率主动回复」（active_reply / possibility_reply）：非 @ 群消息按概率掷骰插话，
  勾选范围写入其 whitelist，**不影响 @ 唤醒的正常回复**。写入回路已实测（写→读→还原一致）。

## [1.0.1-rc.4]

这一版的主题：**群聊防串台 + 面板全面可视化**。

### 变更

- **群聊指令收回免 @ 特权**：`/sid` 这类斜杠指令在群里重新要求**必须 @ 机器人**才触发
  （rc.2 曾放宽为无需 @）。原因：一个群里跑多个机器人时，裸指令会被所有机器人同时响应、互相混淆。
  @ 后的指令仍无外壳透传（rc.2 的核心修复不受影响）；群图片「同一个人 @ 才读取」的暂存机制不受影响。
  私聊指令不变。

### 新增

- **每群回复开关**（会话静音）：面板「成员与权限」的群列表新增开关，关闭后该群所有消息
  （包括 @ 机器人）在桥接就被丢弃，机器人完全不掺和——同样面向多机器人共存场景。
  状态持久化在 `data/muted_sessions.json`，立即生效、无需重启。
- **主动回复白名单可视化**：从手填 textarea 改为「已知群勾选框 + 自定义条目」，
  现有白名单里无法匹配到已知群的条目会自动归入自定义区保留，不会丢。
- **设置页重组**：基础设置按「连接 / 机器人身份 / 消息 / 图片 / 高级」分区，去除重复分组；
  补齐此前面板缺失的配置项（引用回复前缀、图片大小上限、@ 等待窗、联系人切换方式、
  跳过日志开关、AstrBot 配置路径），布尔项正确保存为 true/false。

## [1.0.1-rc.3]

这一版的主题：**管理员与白名单的可视化管理 —— 加一次，处处生效**。

### 新增

- **人员注册表（`state.py` + 新模块 `people.py`）**：以微信 wxid 为稳定身份，
  user_id = `md5(wxid)`。同一个人在**私聊和所有群里是同一个 ID**，
  AstrBot 的 `admins_id` 只需登记一次，管理员身份即全局生效
  （此前群消息的 ID 是 `md5(群ID_昵称)`，每个群都不同，管理员要逐群添加）。
- **群成员名册**：启动时从 WeFlow `/api/v1/group-members` 拉取所有已知群的
  成员名单（wxid ↔ 昵称，多候选名匹配），每 10 分钟自动刷新；据此把群消息
  的发言人解析回 wxid。名册未命中的消息自动回退旧行为（群ID_昵称）并记日志。
- **Web 面板新页「成员与权限」**（`web_panel.py`）：
  - 成员列表：勾选即授管理员，一键「保存管理员」——写入桥接 `data/admins.json`
    并自动同步为 UID 写进 AstrBot `cmd_config.json` 的 `admins_id`；
  - 群会话表：每个已知群的「群 ID + 完整 UMO」一键复制（供 AstrBot 白名单使用）；
  - AstrBot 白名单/主动回复设置：平台 ID 白名单开关与名单、主动回复开关、
    概率、白名单，直接在桥接面板编辑并写入 AstrBot 配置。
- **管理员自动重放**：桥接每次启动把 `data/admins.json` 重放同步到 AstrBot
  （`main.py`），重启/换机无需人工再配。
- **AstrBot 主配置路径**：新增 `astrbot_config_file` 配置项（默认自动探测
  `../AstrBot/data/cmd_config.json`），写回时保留原文件 BOM。

### 变更

- 群消息的 OneBot `user_id` 由 `md5(群ID_昵称)` 改为 `md5(wxid)`。
  群会话本身仍按 `group_id`（= `md5(群ID)`）隔离，**群聊记忆不受影响**；
  仅"发言人身份"变化，AstrBot 侧 `admins_id` 里的旧格式 UID 会失效（由面板同步接管）。

> 注：AstrBot 只在启动时读取 `admins_id`，面板保存后需重启 AstrBot 生效。

## [1.0.1-rc.2]

对应上游 tag `v1.0.1`。这一版的主题是：**让群聊里的内置指令能用、不再被"外壳"吃掉**。

### 修复

- **群聊内置指令全部失效**（`/sid`、`/help`、`/reset` …）：桥接会把群消息包装成
  `某某在群某某中说：<原文>` 再发给 AstrBot，于是 AstrBot 看到的文本**不以 `/` 开头**，
  内置指令被当成普通聊天丢给大模型，用户永远等不到回复（私聊没有这层包装，所以私聊一直正常）。
  现在以 `/` 开头的群消息**原样透传**，不套外壳。
- **群聊里裸指令被提前丢弃**：`mention` 模式下，未 @ 机器人的群消息会被桥接直接跳过，
  `/sid` 这类指令还没到 AstrBot 就没了。现在以 `/` 开头的消息**无需 @** 也放行，
  与 AstrBot 自身的 `wake_prefix` 语义一致。
  （只放宽"是否放行"，**不影响图片门槛** —— 群图片仍只认同一个人的真实 @。）

> 注：私聊路径本就没有这层包装，`/sid` 在私聊里始终可用。改动只针对群聊。

## [1.0.1-rc.1]

对应上游 tag `v1.0.1`。这一版的主题是：**让桥接能长期稳定地跑起来**。

### 修复

**发送链路（UIA）**
- 消息被写进微信左侧搜索框：聊天输入框 `mmui::ChatInputField` 在控件树第 18 层左右，上游遍历深度上限 14 找不到，回退逻辑把唯一的另一个 EditControl（搜索框）当成了输入框。深度改为 26，并按类名精确定位
- 找不到合适输入框时不再退化为使用搜索框，直接中止
- `uiautomation` 2.x 移除了 `IsValuePatternAvailable` 与 `Control.SetValue`，原代码抛异常后退化成 `SendKeys`（发给当前焦点控件 → 落进搜索框）。改为 `GetPropertyValue(PropertyId…)` + `GetValuePattern().SetValue()`
- 发送按钮定位错误：原按"名称为空或含发送/空"匹配，抓到的是左侧栏无名图标（点了没反应，表现为"字填进输入框但发不出去"）。改为按类名 `mmui::XOutlineButton` + 名称「发送」定位
- 发送结果判定：改为依次尝试 发送按钮 → Enter → Ctrl+Enter，以「输入框是否清空」为唯一成功判据；失败会在日志明确报出，不再假装成功
- 发送前先 `SetFocus()`，避免 `SendKeys` 打到别的控件
- 窗口句柄：上游用 `Qt51514QWindowIcon` / `WeChatMainWndForPC`，微信 4.x 实际是 `mmui::MainWindow`（标题 `Weixin`）

**会话与身份**
- 会话 ID 用 `hash(wxid)`：**Python 对字符串的 hash 每进程随机化**，桥接一重启同一联系人就变成新会话，AstrBot 面板里表现为"每个私聊/群聊都出现两遍"。改为 MD5 前 8 字节，跨重启稳定
- 群 ID 改用 `xxx@chatroom` 而非群名，群改名不再产生新会话
- SSE 的 `groupName` 偶发缺失时，上游会用 `sourceName`（也是原始 ID）当群名，面板显示成 `xxx@chatroom`。改为持久化「微信 ID → 显示名」缓存（启动时从 WeFlow 全量预取 + 消息流回写）

**消息流**
- 推送期间到达的新消息会一直压在缓冲里（上游 `processing=True` 时不再排期）→ 推送完成后重新排期
- 自回复去重完全失效：上游 `_sent_recently` 只判断、从不写入，机器人会把自己的回复当成新消息再回一遍 → 发送时记录，接收时比对
- 本地请求走系统代理导致 502：在 `config.py` 代码层面补 `NO_PROXY`，不再依赖启动脚本
- `processed_ids` 无上限增长 → 加 FIFO（上限 5000）

### 新增

- **会话列表点击切换**：先在左侧会话列表按名字点击（精确 > 前缀 > 包含），失败再退回 Ctrl+F 搜索；切换后用标题栏校验是否真的切过去了。`switch_method`：`auto`（默认）/ `list` / `search`
- **群图片门槛**：图片必须与**同一个人的 @ 属于同一次请求**才读取——@ 之前发的先暂存等 @，@ 之后紧跟的直接读；换人 @ 不消费别人的暂存，超时作废。避免群里任何人发图都触发回复
- **图片理解两条路**（`image_caption_model`）：留空 → 图片原样以 `base64://` 段交给 AstrBot（由它用主模型直看或走转述模型）；填了 → 走上游的桥接侧描述（取图落盘 → 描述模型 → 发文字）。上游的描述体系完整保留
- **只读 OneBot 接口**：`get_login_info` / `get_group_info` / `get_group_member_info` / `get_group_member_list` / `get_group_list` / `get_friend_list` / `get_stranger_info` / `get_msg`。此前一律回空 `{}`，AstrBot 拿不到群名与成员昵称（实测它每次解析 @ 都会调 `get_group_member_info`）
- **被丢弃的消息会打日志**：`⏭️ 跳过 群[…] 某人: 原因（30s 内累计 N 条）`，按"会话+成员+原因"节流，可用 `log_skipped_messages` 关闭
- 新增配置：`switch_method`、`log_skipped_messages`、`quote_reply_prefix`、`web_host`、`image_mention_window`、`image_max_bytes`
- 联系人名持久化缓存（`data/chat_names.json`，已被 gitignore）
- 项目标识：`PROJECT_NAME = "Akasha-WeChat_RC"` + `VERSION` 文件，启动日志首行打印

### 变更

- `web_host` 默认 `0.0.0.0`（局域网可访问），只想要本机访问改 `127.0.0.1`
- `senders.create_sender()` 在 `send_method=weflow_api` 时额外打一条警告：WeFlow 实测**没有发送接口**（`/api/v1/message`、`/api/v1/send` 等均 404），该路径必然失败，正常请用 `uia`

### 其他

- 补齐维护文档：`README.md`（fork 说明）、`AGENT.md`（约定与踩坑）、`CHANGELOG.md`（本文件）、`VERSION`、`.gitignore`
- 确立维护约定：不删上游代码、同文件编辑串行、隐私红线、长驻程序用可见窗口启动

### 已知限制

- 微信原生「引用回复」气泡做不了（需要客户端右键菜单操作，UIA 不可靠）；`quote_reply_prefix` 只是文本模拟，默认关闭
- 群成员完整名单与群人数取不到（WeFlow 无对应接口），`get_group_member_list` 只含发过言的成员
- AstrBot 在拿不到群人数时会用 `len(成员列表)` 兜底，因此该数字偏小——已知，不编造
