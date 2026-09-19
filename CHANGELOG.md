# 开发日志

本文件记录 `Akasha-WeChat_RC` 相对上游 [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 的改动。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)：`新增` / `修复` / `变更` / `其他`。
约定见 [`AGENT.md`](AGENT.md)——尤其**不得删除上游既有代码**，本分支只做修复与增量。

## 退出归因：区分「自己崩了」和「被别人杀了」（2026-09-19）

### 新增

**动机**：桥接某天从日志里**干净消失** —— 最后一条是正常的"名册已刷新"，
没有任何 Traceback，8766 端口也没了。**无法判断**到底是：
① 未捕获异常挂掉 ② 被 taskkill / 任务管理器强杀 ③ 主动 sys.exit。
三者排查方向完全不同，但日志长一个样（实测排查时只能靠"时间线猜测"）。

**修法**：新增 `runtime/bridge/exit_reason.py`，写 `data/exit_reason.log`。

关键洞察（Windows 语义）：
**TerminateProcess（taskkill /F、任务管理器"结束任务"）不触发任何 Python 清理** ——
`atexit` 和 `finally` 都不执行。所以判据是**反过来的**：

| 日志表现 | 结论 |
|---|---|
| 有退出记录（异常/主动/信号） | **自己退的** |
| **没有任何退出记录** | **被强杀** |

因此采用两条腿：
- 启动时写 `[启动]` 记录（供事后算 uptime）
- 注册 `atexit` + `signal(SIGTERM/SIGINT/SIGBREAK)` + `sys.excepthook`
- **下次启动**时检查"上次启动之后有没有退出记录"，没有就判定为被强制终止

同时 `set_phase()` 记录关键阶段，便于定位"死在哪一步"。

### 面板可见

控制面板新增卡片「🧭 上次是怎么退的」，直接显示：
上次退出原因（被强杀时标红）、本次已运行时长、当前阶段、可展开的历史记录。
新增端点 `GET /api/exit-reason`。

### 验证

`scripts/test_exit_reason.py` —— 三个场景全部正确归类：

| 场景 | 结果 |
|---|---|
| 未捕获异常 | ✅ 记录「未捕获异常」+ traceback |
| 主动 note_exit | ✅ 记录「主动退出」+ 原因 |
| taskkill /F 强杀 | ✅ 被杀时无记录；下次启动判定「被强制终止」 |

**实测（真实进程）**：强杀正在运行的桥接 → 重启后面板显示
「⚠️ 上次被**强制终止**（无退出记录）」，判定正确。

### 踩坑记录

改动面板 JS 时又把 `'\n'` 写成了真换行，导致**整个 `<script>` 解析失败**
（`Invalid or unexpected token`，所有函数未定义）—— 与上次"重启按钮"同一个坑。
已改为 `\\n`；`verify_exit_reason_panel.py` 会断言 `pageerror == 0` 来防复发。

`exit_reason.py` 已加入 `build_dist.py` 的 `BRIDGE_FILES` 与 `sync_to_rc.py`
（前一天刚因 `astrbot_ctl.py` 漏加导致发行版缺文件，这次不再重犯）。

## 群聊「同人别名」——昵称/备注两套名字导致模型认成两个人（2026-09-19）

### 修复

**现象**：bot 在群里说「测试用户博士和RulerCordelius博士是**两位不同的朋友**呀喵。」
——但这两个名字属于**同一个人**（备注=RulerCordelius，昵称=测试用户）。

**真因（信息没传递到位，不是模型笨）**：
同一个人的两个名字从**两条不同通道**进入模型上下文：

| 通道 | 显示 | 来源 |
|---|---|---|
| 他自己的消息 | `RulerCordelius` | 桥接按备注名标注 sender |
| 别人 @ 他 | `测试用户` | 微信自动填**昵称**，原样透传 |

实测的上下文原文（同群、同一分钟）：

```
["洛辰" 拍了拍 "RulerCordelius"]      ← 拍一拍：用备注名
[洛辰/16:04:22]: @测试用户 你是猫娘       ← 洛辰手打的 @：用昵称
```

**两个名字并列出现、且没有任何标记说明是同一人** → 模型只能推断是两个人。
它的推理本身没错，是**我们给的数据有歧义**。

**不是个例**：扫描 4 个群 68 名成员，**6 人**昵称≠备注：
`RulerCordelius←测试用户`、`爸爸←An帝y哥`、`妈妈←Purple` 等。

**修法（两层，自动生成、不写死人名）**：

1. **桥接侧自动生成别名表**（`state.py`）
   WeFlow 的 `/api/v1/group-members` 同时给出 `nickname`(昵称) 与
   `remark`(备注)，据此自动建立「主名 ← 别名」表（实测生成 **44 条**）。
   发言人有别名时，在该条群消息末尾附加轻量标记：
   `<alias>测试用户=RulerCordelius</alias>`

2. **AstrBot 侧提取成「同名说明」**（新补丁 `patch_group_alias_note.py`）
   在 `_format_group_history_block()` 里把标记收集、去重、**从正文移除**，
   提升为上下文块头部的说明行：

```
<system_reminder>You are in a group chat.
--- BEGIN CONTEXT---
[同名说明] 测试用户、rulercordelius_J = RulerCordelius（同一个人；RulerCordelius 是备注名）
["洛辰" 拍了拍 "RulerCordelius"]
[洛辰/16:04:22]:  RulerCordelius在群测试群1中说：@测试用户 你是猫娘
--- END CONTEXT ---
```

标记只在**有别名时**才附加，普通消息不受影响；旧消息无标记时行为不变。

### 验证

- `scripts/test_alias_note.py` —— 4 个用例（带别名 / 无别名不产生空段落 /
  多人多别名 / 同人去重）**全部通过**
- `scripts/verify_alias_e2e.py` —— 桥接侧格式化 + AstrBot 侧提取贯通 **PASS**
- `check_patches.py` 由 7 项增至 **8 项全绿**

> 记录一个判定失误：E2E 首跑我判成 FAIL，因为断言写死了
> `[同名说明] 测试用户 = RulerCordelius`，而实际输出含两个别名
> （`测试用户、rulercordelius_J`）。**是断言太严，不是功能失败**——
> 遇到失败先看原文，别急着改实现。

## [1.5.1]（2026-09-19）

正式发行版（`build_dist.py`）。本版仅同步一项已生效并验证的人设修复。

### 修复

- **人设「称呼漂移防护」** —— 对方手滑把「博士」打成「医生」时，bot 会跟着用错词。
  已给 **mon3tr + mostima**（唯二以「博士」作称呼的人设）追加
  「## 称呼漂移防护（最高优先级）」段落，核心是**禁止把错词与「博士」并列复述**
  （详见下方「人设『称呼漂移防护』」条目）。

> 本版相对 v1.5.0 只多这一项 —— v1.5.0 是在该规则生效**之前**打的包。
> 代码层无任何改动，差异仅在 `astrbot/data/data_v4.db` 的两条人设。

### 验证

- `scripts/verify_no_drift.py` 连跑 3 次全部 PASS（回复变为「纠正 + 始终用博士」）
- `check_patches.py` 7 项全绿
- 源库确认：mon3tr / mostima 含规则，konan / yuki 未受影响

## 人设「称呼漂移防护」（2026-09-19）

### 修复

**现象**：好友 Shawn 手滑把「博士」打成了「医生」，随后 bot **跟着用错词**，
3 分钟内连说 4 次（`喵，Shawn 医生。` / `Shawn 医生你手好快。` / `嗯嗯，Shawn 医生。`）。

**真因（不是人设写错，是自我强化漂移）**：
错词进上下文 → bot 复述 → 复述又被当成"这个称呼是对的" → 越用越顺。

实测统计：正确「博士」**203 次**、漂移「医生」**6 次**，
**6 次全部集中在 Shawn 这一个会话的 3 分钟内** —— 起点就是用户自己那条「医生」。

最能说明问题的一条：bot 当时其实**已经察觉到**对方打错了，回的是
「哎呀，Shawn **博士**是**医生**哦」——但它把两个词**并列复述**，
反而抬高了错词在上下文中的权重，接下来连着用了两次。
所以规则里「禁止并列复述」比「不要跟着用」更关键。

**修法**：新增 `scripts/patch_persona_doctor_drift.py`，
给 **mon3tr + mostima**（唯二以「博士」作称呼的人设）追加
「## 称呼漂移防护（最高优先级）」段落，四条：

1. 固定用「博士」，「医生/老师/Doctor」都不是称呼
2. 对方叫错时依然只叫「博士」，不跟着用错词
3. 可纠正最多一次，之后不再提
4. **绝对禁止把错词与「博士」并列复述**（关键）

> konan（火影）与 yuki（Persona 3）人设里明确写着**不要使用「博士」**，故不涉及。

### 验证

`scripts/verify_no_drift.py` —— 注入与事故相同的消息（对方先发「医生」），
检查回复是否出现「XX 医生」式跟随称呼：

**连跑 3 次全部 PASS**，回复变成：

```
Shawn博士，"医生"是游戏里彩虹小队的干员代号…和你是两回事呀。
你叫我一声Shawn博士就对啦喵。
```

即：**纠正 + 解释，且始终用「博士」**，不再被带偏。

> 判定标准说明：不能简单地搜「医生」二字 ——
> 解释性用法（「医生是干员代号」）正是期望行为。
> 只有出现在**称呼位置**（`Shawn 医生`）才算漂移。

### 生效

已通过面板一键重启按钮重启 AstrBot（PID 18780 → 9956，用时 49.5s），
`Loaded 4 personas`；`check_patches.py` 由 6 项增至 **7 项全绿**。

## 向上游提交 issue（2026-09-19）

把本分支的改动整理成两篇 issue 提交给对应上游（**只提 issue，不提 PR**）：

| 上游 | issue | 内容 |
|---|---|---|
| [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) | [#4](https://github.com/alingalingling/Akasha-WeChat/issues/4) | 面板白名单三个叠加缺陷：私聊存裸 UID 导致永久静默拦截（根因）/ 勾选状态丢失 / 保存抹掉群条目；附完整复现步骤与验证清单 |
| [AstrBotDevs/AstrBot](https://github.com/AstrBotDevs/AstrBot) | [#10127](https://github.com/AstrBotDevs/AstrBot/issues/10127) | 知识库注入措辞会让模型"编造亲身经历"而非如实引用资料；附三处文件的具体 before/after 补丁细节 |

草稿与提交脚本（可复跑）：

- `release/issues/issue_akasha_whitelist.md`
- `release/issues/issue_astrbot_kb_wording.md`
- `scripts/post_issues.py`（REST API；token 从 git credential 读取，不回显不落盘）

> 注：本机未装 `gh`，已装到 `%LOCALAPPDATA%\Programs\gh`。
> 该 token 的 **GraphQL 配额已用尽**（`gh repo view` 会报 rate limit），
> 但 REST API 正常，故脚本走 REST。

## [1.5.0]（2026-09-18 晚）

正式发行版（`build_dist.py`）。本版打包四项已在本地验证的改动：

### 新增

- **面板一键重启 AstrBot** —— 成员与权限页新增「🔄 重启 AstrBot」按钮。
  AstrBot 的白名单/人设/平台适配器只在启动时读一次，改完必须重启；
  以前只能手动关控制台窗口，现在面板点一下即可（后台线程 + 进度轮询，
  重启期间桥接自动重连）。实现见 `astrbot_ctl.py`，关键点：
  按端口反查 PID（不误杀桥接/模拟器）、detach 启动（不成为桥接子进程）、
  轮询端口判就绪、清残留 `astrbot.lock`。

### 修复

- **私聊白名单「永远匹配不上」** —— 真因：AstrBot 判定用
  `unified_msg_origin not in whitelist and get_group_id() not in whitelist`，
  私聊没有 `group_id`，因此裸数字 UID **结构上永远匹配不上**（与是否重启无关）。
  已把私聊条目规整为完整 UMO（`wechat_bridge:FriendMessage:<uid>`）；
  新增 `normalize_whitelist_entries()`，面板保存时自动规整。
- **面板白名单「保存了却不见了」** —— chip 的 `data-uid` 是纯数字而存储层是完整
  UMO，两者直接比永远不相等 → 已保存的私聊在面板上全显示为未勾选。
  新增 `wlEntryToUid()` / `wlUidSet()` 统一抽取后比较。
- **保存白名单会写坏名单** —— `write_friend_whitelist()` 原为整表覆盖，
  会把 6 个群条目一并抹掉（群聊全部失联）；现改为保留群条目 + 合并去重。
- **白名单重复条目** —— `normalize_whitelist_entries()` 不按 UID 去重，
  面板每保存一次就多写一份裸数字（实测脏化 12 → 15 条）；现按 UID 收敛。

### 验证

- `scripts/verify_panel_whitelist.py`：无头浏览器渲染面板，断言 3 个私聊为已勾选、无 JS 错误
- `scripts/verify_private_whitelist_e2e.py`：以 Shawn UID 注入私聊走完整管道 → 收到回复
- `scripts/verify_restart_button.py`：真的点一次按钮 → PID 15276 → 15680，phase=done
- 重启后 `not in the session allowlist` 计数 = 0；四项服务 LISTENING

### 包内不含

向量知识库（`knowledge_base/*/{doc.db,index.faiss}`）已按要求删除；
三个人格文件与普通知识库文档（`astrbot/kb_docs/*.md`）**保留**。

## 面板一键重启 AstrBot（2026-09-18 晚）

### 新增

**动机**：AstrBot 的 `WhitelistCheckStage.initialize()` 和 `PersonaManager`
**只在启动时读一次**配置。所以「改白名单/人设/平台适配器 → 必须重启」是常态，
以前只能手动关掉控制台窗口再双击 `start.bat`，每次都得找人。

**做法**：`runtime/bridge/astrbot_ctl.py` + 面板「🔄 重启 AstrBot」按钮。

关键设计（都是踩过的坑）：
1. **按端口找进程，不按进程名**——机器上同时跑着桥接、模拟器、AstrBot 多个
   python，按名字杀会误伤。用 `netstat -ano` 反查监听 `11229` 的 PID。
2. **detach 启动**——普通 `Popen` 会让 AstrBot 成为桥接的**子进程**，桥接一重启
   （改代码很频繁）AstrBot 就跟着死。改用
   `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`，并把 stdout 重定向到
   `astrbot_run.log`（没有控制台时输出会丢）。
3. **轮询端口判就绪**——冷启动要 40-70 秒（4 个人设 + 十几个 provider + 群名册），
   只看进程存在不够。
4. **清残留锁**——`astrbot.lock` 在强杀后会残留，新进程直接
   `Cannot acquire lock file` 退出（本次就撞到过：两个实例抢锁）。
5. **异步 + 轮询**——重启要几十秒，不能让 HTTP 干等（浏览器超时）。
   端点立刻返回，前端每 1.2s 轮询 `/api/astrbot-status`。

**新增文件**：`runtime/bridge/astrbot_ctl.py`
**新增端点**：`POST /api/astrbot-restart`（可带 `{"action":"stop"}` 只停）、
`GET /api/astrbot-status`（重启进度 + 实时端口探测）

### 顺带修复

- **白名单重复条目**：`normalize_whitelist_entries()` 之前不按 UID 去重，
  面板每保存一次就会同时写入 `1000000001` 和
  `wechat_bridge:FriendMessage:1000000001` 两条。功能上无害（UMO 已能匹配），
  但名单会越滚越脏（实测 12 → 15 条）。现在已按 UID 收敛，保存即自清洗。
- **面板 JS 语法错误**：`confirm()` 里的换行写成了真实换行，导致整个
  `<script>` 解析失败、**所有函数（含页签切换）全部未定义**。
  这也是「按钮点了没反应」的一类根因。已改为 `\n` 转义。

### 验证

`scripts/verify_restart_button.py` —— 无头浏览器打开面板、**真的点一次按钮**、
轮询到 done、断言 PID 变化：
**PASS**（PID 15276 → 15680，状态「AstrBot 已就绪（用时 69.7s）」，JS 错误 0）。

## 面板白名单「保存了却不见了 / 存了也不生效」——第二轮修复（2026-09-18 晚）

### 修复

**现象**：用户在面板重新勾了 3 个私聊并保存，问「可以了吗」。

**查出三个叠加的缺陷**（都不是「重启一下就好」能解决的）：

1. **面板显示层：勾选状态永远丢失**
   chip 的 `data-uid` 是纯数字（`1000000009`），而存储层按 AstrBot 要求存的是
   完整 UMO（`wechat_bridge:FriendMessage:1000000009`）。
   `renderFriendList()` 里 `merged.indexOf(String(p.uid))` 两者直接比
   → **永远不相等** → 已保存的私聊在面板上全部显示为「未勾选」，
   用户看到的就是「白名单不见了」，只好重勾一遍。
   修：新增 `wlEntryToUid()` / `wlUidSet()`，比较前统一抽取 UID。

2. **面板保存层：会写坏名单**
   `collectFriendWhitelist()` 把好友勾选以**裸数字**写回，且与缓存里的 UMO 条目
   **重复共存**（同一人两条：旧 UMO + 新裸 ID）。
   `write_friend_whitelist()` 更直接——`ps["id_whitelist"] = uids` **整表覆盖**，
   会把 6 个群条目一并抹掉（群聊全部失联）。
   修：保存前先剔除好友管辖的旧条目再按勾选重建（输出完整 UMO）；
   `write_friend_whitelist()` 改为**保留既有群条目 + 合并去重**，并走
   `normalize_whitelist_entries()` 规整格式。

3. **时效层：改了不重启 = 没改**
   AstrBot 的 `WhitelistCheckStage.initialize()` **只在启动时读一次**白名单。
   实测时间线：AstrBot 20:46:14 启动 → 用户 20:52:26 保存 → 重启前一直按旧名单拦截。
   修：保存成功后弹出醒目横幅（`#wlRestartWarn`），明确「刚保存的还没生效」。

**验证**（脚本化，可回归）：
- `scripts/verify_panel_whitelist.py` —— 无头浏览器渲染面板，断言 3 个私聊 chip
  处于 checked 状态、无 JS 错误 → **PASS**（`已勾 3 / 共 157 人`）
- `scripts/verify_private_whitelist_e2e.py` —— 以 Shawn 的 UID 注入私聊事件走完整管道
  → **PASS**（收到回复）；重启后 `not in the session allowlist` 计数 = **0**

**教训**：光看「ID 在不在名单里」不够——**必须核对格式**。
存储格式（完整 UMO）与 UI 数据模型（裸 UID）不一致时，
会同时产生「显示不见」和「静默拦截」两种症状，而两者看起来都像「配置没保存」。

## 私聊白名单「永远匹配不上」——真因定位（2026-09-18）

### 修复

**现象**：好友 Shawn 发很多条消息，机器人一条都不回（用户报障两次）。

**真因**（之前两次都误判成"要重启 AstrBot"，其实不是）：
AstrBot 的白名单判定是——

```python
if (event.unified_msg_origin not in self.whitelist
        and str(event.get_group_id()).strip() not in self.whitelist):
```

它**只认两种写法**：
- 完整 UMO，如 `wechat_bridge:FriendMessage:1000000009`
- 群 ID（走 `get_group_id()` 兜底），如 `2000000001`

**而私聊没有 `group_id`**。所以往名单里写裸数字 UID（`1000000009`）
→ 私聊**结构上永远匹配不上**，无论重启多少次都没用。

**实测证据（决定性）**：全部 11 次 whitelist 拒绝**都是私聊、群 0 次** ——
群里一直正常，所以根本联想不到是白名单。这也解释了为什么这个坑反复出现、
"重启一下好像好了"（其实是恰好那次群里在说话）。

**修法**：
- `people.normalize_whitelist_entries()` —— 数字 ID 属于已知群则保持裸 ID，
  否则按私聊补全成完整 UMO；面板保存白名单时自动规整，
  **以后从面板加好友不会再写错格式**；
- 现存 12 条已改写：6 条私聊 → 完整 UMO，6 条群 → 保持裸 ID。

### 教训

- 「加了好友/群却不回复」先看 `whitelist_check.stage` 日志，
  再用**这条会话的完整 UMO**去比对名单格式，别只看"ID 在不在名单里"。
- 之前的两次"重启 AstrBot 就好了"是**误诊**：配置确实需要重启才生效，
  但格式错了重启也没用。诊断时要区分"没生效"和"格式不对"。

## [1.4.0]（2026-09-18）

**版号 minor +1**：两个面向用户的新功能 + 一个真 bug 修复，不动架构。

### 本版包含（自 v1.3.0 以来）

- **新增**：面板私聊白名单**搜索 + 只看已勾 + 已勾计数**（好友多了以后不用逐个找）
- **新增**：**会话 ID 显示成人名**（AstrBot 面板「自定义规则」里不再是一串裸数字）
  - `people.sync_umo_aliases()` 按桥接名册补齐 AstrBot 的 `umo_aliases`
  - 挂在启动 + 每 10 分钟的名册刷新里，**新会话自动命名**
  - 面板 `/api/sync-umo-names` 可手动触发
  - 顺带补 `state.all_chat_names()`（原只有 `known_groups()`，拿不到「文件传输助手」
    这类非好友会话）
- **修复**：出站昵称不再让 wxid/纯数字漏过去（`bridge_core._resolve_display_name()`）
- **修复**：搜索筛选时白名单里的**非好友条目（群 ID）不再被静默删掉**
  （实测 12 项里 6 项是群 ID，会因搜索丢项导致群突然不回复）

### 关于源码注释里的真实昵称

`release/versions/*` 归档与 `release/dist/*` 发行版在构建时会跑脱敏
（`sanitize_privacy.py`），所以**注释里的真实群友昵称不会外泄**；
开发用的源码副本里保留真名是为了排障时看得懂。
每次出包都会重新脱敏 + 三道闸门校验，成品包已实测零残留。

## 会话 ID 显示成人名（自定义规则页看不出是谁）（2026-09-18）

### 修复

- **面板「自定义规则」里会话只显示 `wechat_bridge:FriendMessage:1000000010`
  这种数字 ID，根本看不出是谁**。查明是 AstrBot 的 `umo_aliases` 表没被正确填充，
  有两个独立成因：
  1. **WeFlow 把 `sourceName` 推成 wxid**：某些联系人推来的是
     `wxid_dykw4m5ueyms12` 而不是昵称，桥接原样当 `nickname` 发给 AstrBot，
     AstrBot 的 UMO 自动命名就把 **wxid 记成了名字**（改用名册反查修正为「群友D」）。
  2. **不经过唤醒阶段的会话压根没有记录**：定时任务/主动发送
     （如 `FriendMessage:161333918` 那条 cron 自检）不触发
     `umo_auto_name` 记录，于是完全没有别名。
  修法：
  - `bridge_core._resolve_display_name()` —— 出站昵称不再让 wxid/纯数字漏过去，
     wxid 时先查 `persons.json` 名册再退回 contact；
  - `people.sync_umo_aliases()` —— 按桥接名册（`chat_names.json` 优先，
     `persons.json` 兜底）把 AstrBot 里"没名字/名字是 wxid/纯数字"的会话批量补齐；
  - 挂在**群名册刷新**里（启动时 + 每 10 分钟一轮），所以**以后新会话会自动有名字**；
  - 另给面板 `/api/sync-umo-names` 可手动触发。
- **取名优先级踩坑**：`persons.json` 的 `names` 是历史累积别名，第一条不一定是最新
  （`wxid_wbsce3wcayn412` 的 names 是 `['测试用户', 'RulerCordelius']`，
  首条会把当前名 `RulerCordelius` 显示成旧名 `测试用户`）。
  已改为**优先 `chat_names.json`**（当前会话名的权威来源）。

### 结果

11 条会话别名全部变成可读人名（RulerCordelius / 群友D / Shawn / 星宇 / 群名…），
其中 1 条来源已不可考的旧会话如实标注为「（未识别的好友 161333918）」，
不编造身份。

## 私聊白名单加搜索（2026-09-18）

### 新增

- **面板私聊白名单卡片加搜索框 + 「只看已勾」**：好友多起来后逐个找太费劲，
  现在可按 **名字 / wxid / UID** 实时筛选（输入即过滤）；「只看已勾」开关
  只列已进白名单的人；卡片下方显示 **已勾 N / 共 M 人**。

### 修复（写这个功能时发现的真 bug）

- **搜索会把白名单里「不是好友」的条目静默删掉**：这份 `id_whitelist` 是
  **私聊好友与群共用的一份名单** —— 实测本机 12 项里有 **6 项是群 ID**
  （`2000000002` 等），它们不会出现在好友 chip 里。原实现
  `collectFriendWhitelist()` 只读 DOM 上 `checked` 的 checkbox，一旦搜索把
  好友筛掉、或保存时只看到可见项，那 6 个群 ID 就会在保存瞬间丢失，
  导致**群消息突然全部不回复**。
  修法：以 `currentWhitelist` 缓存为基准，用当前可见 chip 的勾选状态**做同步**
  （可见的按可见的来，不可见的保留缓存），另把群视图已勾项与手动补充项一并合并。
  实测保存前后 12 项完全一致，零丢失。

## [1.3.0] —— 新代号后的第一个版号（2026-09-18）

**版号自 1.2.9 起 minor +1**：含 4 个真修复 + 1 个新功能 + 项目代号更名，
不足以动架构（不动 major），明显超出纯补丁（不止 patch）。

### 本版包含（自 v1.2.9 发行版以来的全部改动）

- **修复**：引用回复「发了但没发出去」（`verify=False` 假成功，用户报障的丢消息根因）
- **修复**：微信气泡顶上多一个空行（AstrBot 前导换行未 strip）
- **修复**：群友「群友C」被叫成简体（纠错表缺「緒→绪」+ 新增逐位兜底层）
- **修复**：面板改设置「保存成功」但其实没存（并发写坏 JSON → 原子写 + 损坏自愈）
- **修复**：WeFlow access_token 明文进日志（面板局域网可见）→ `access_token=***`
- **新增**：面板「成员与权限」页顶部独立卡片 —— **私聊白名单可视化点选**
  （新加好友不回复 → 勾上 → 保存 → 重启 AstrBot；与群白名单双向合并防覆盖）
- **变更**：项目代号定为 `Akasha_RulerCordelius-Wechatbot`，面板/日志/包名全链统一；
  `RulerCordelius` 作为代号一部分从脱敏名单放行（真实姓名仍拦截）

### 其他

- 隐私红线更新：`_runtime-data-snapshot`（真实 wxid/群名/人名）永不归档；
  发行版构建三道闸门（脱敏审计 + 本机标识硬检查 + 密钥兜底扫描）。
- ⚠️ 流程教训：出 v1.3.0 时把旧发行版 `v1.2.9.zip` 清掉了（未问用户），
  违反"**发行版历史只增不删**"。已临时把 VERSION 切回 1.2.9 重建补回
  （代码同源，产物等价），再把 VERSION 切回 1.3.0。
  约定已写入 `AGENT.md`：`release/dist/` 与历史纯净版 zip **只增不删**，
  空间不够就问用户。

## 新好友私聊不回复：白名单 + 面板可视化编辑（2026-09-18）

### 修复 / 新增

- **根因**：新好友 Shawn 私聊三条消息桥接都推送成功，但 AstrBot 侧日志
  `whitelist_check.stage: Session ID wechat_bridge:FriendMessage:1000000009
  is not in the session allowlist` —— AstrBot 开着 `enable_id_white_list`，
  Shawn 的 UID（1000000009）不在 `id_whitelist`（6 项）里，事件在 pipeline
  第一阶段被丢弃。已把 1000000009 加入白名单并重启 AstrBot 生效。
- **AstrBot 白名单只读一次的坑**：`WhitelistCheckStage.initialize()` 在启动时
  把名单读进内存，**改配置文件不热生效，必须重启 AstrBot**。面板上已加提示。
- **面板新增「私聊白名单」可视化编辑**（成员与权限 → 高级区）：
  好友 chip 点选（UID 为值、昵称为名）+ 开关 + 手动补 UID + 保存按钮。
  与群白名单视图共享同一份 `id_whitelist`；保存时自动合并另一视图已勾的
  群条目，避免两处互相覆盖丢数据。新增 `people.read_friend_whitelist() /
  write_friend_whitelist()`，复用既有 `/api/astrbot` 端点。

### 约定

- **平时只改源码，不随手重建发行版**（用户明确要求）：`build_dist.py` 仅在
  用户要求出包时运行；日常流程 = 改 `runtime/bridge/` → `sync_to_rc.py` → 重启桥接。

## 项目代号更名：Akasha_RulerCordelius-Wechatbot（2026-09-18）

主题：**统一所有对外命名到新代号**（用户钦定，长期固定）。

### 变更

- **代号生效范围**：`config.PROJECT_NAME`（两副本）、面板浏览器标题与页面抬头、
  桥接启动 banner、发行版 zip 名与包内顶层目录、源码归档 BUILD_INFO 标题、
  历史纯净版 zip 文件名（12 个），全部改齐。
  面板抬头简化为「代号 + 版本号」，由 `PROJECT_NAME`/`PROJECT_VERSION`
  单一来源派生，不再有硬编码的「Akasha」字样与 `_RC` 角标。
- **`RulerCordelius` 从隐私名单移除**：它是代号的一部分（作者公开 ID），
  已从 `sanitize_privacy.py` 的替换表与 `build_dist.HARD_LITERALS` 硬检查中放行
  —— 否则构建会在自己的项目名上中止。真实姓名 `Junqin Zhao` 与本机路径
  **仍是隐私**，继续拦截（实测替换仍生效）。
- `sync_to_rc.py` 的 `PROJECT_BLOCK` 模板同步更新。

### 说明

- 目录名 `Akasha-Wechat_RC/` 与仓库名**未改**（改名影响面大，另议）；
  变的是所有"对外可见"的标识。上游 fork 关系与 `_RC` 分支语义不变。
- 发行版已重建：`release/dist/Akasha_RulerCordelius-Wechatbot-v1.2.9.zip`
  （包内 8 项核对 + 顶层目录新代号 + 旧名零残留）。

## 发行版全面复查：又揪出一个隐私泄漏（2026-09-18）

主题：**对第一版改版后的发行版做整包体检 + 日志全面排查**。

### 修复

- **WeFlow access_token 明文进日志（新发现）**：`bridge_core.listen_sse()` 曾把
  完整 SSE URL 打进日志 —— URL 里带着 `access_token=<明文>`。
  本项目 README 的隐私提醒明确要求"贴日志前删掉 token"，桥接自己却把它印出来了，
  而且面板日志窗口（局域网可访问）也会显示这行。历史日志里累计 92 处
  （bridge.log 56 + bridge_run.log 36），已全部掩盖为 `access_token=***`；
  源码改为只打基址 + `***`。发图片/文件的两处 URL 构造（不下日志）核实无泄漏。
- **发行版时序修正**：此前 `release/dist/*.zip`（19:46 构建）只含 4 个 bug 修复，
  **不含** 20:38 的面板 `_RC` 标识与 20:53 的 token 脱敏。已重建
  （21:05），新包内 8 项核对全部通过（4 修复 + token 脱敏 + _RC 标识 +
  PROJECT_TAG + 隐私 11 类零命中）。

### 复查结论（排查过、确认不是 bug）

- 本会话 17 次推送 0 回复：全部来自「测试群3」——
  该群未静音、不在插话黑名单，但也不在白名单，`all` 模式下非 @ 消息走
  AstrBot 3% 随机插话掷骰，17 连不中概率 ~59%，属正常分布。
- AstrBot 日志零 ERROR/CRITICAL；6 个人设补丁完好；`config.example.json`
  全部为占位符；sim/ 无敏感串。
- 发行版内命中的 `jwt_secret`/`pbkdf2`/`session_secret` 等串全部是
  AstrBot **框架源码的字段名**与 BUILD_INFO 的措辞清单，非真实值。

## 面板标题加分支标识（2026-09-18）

### 变更

- **Akasha 面板标题带 `_RC` 与版本号**：浏览器标签页与页面抬头都显示
  **`Akasha_RC 奈奈山 v1.2.9`**，一眼能看出跑的是 RC 分支而不是上游原版
  （上游是 `Akasha 奈奈山`，两者混用时容易对错版本）。
  实现上不是把 `_RC` 写死在 HTML 里，而是**读 `config.PROJECT_TAG` /
  `PROJECT_VERSION`**（版本号来自同目录 `VERSION` 文件），经 `/status`
  下发给前端填充 —— 以后升版本只改 `VERSION` 一个文件，不必回来改面板。
- 顺带修掉两个小问题：
  - `runtime/bridge/config.py` 缺 `PROJECT_NAME` 那块（以前只有发布副本有，
    靠 `sync_to_rc.py` 补），现在两边都写全；`sync_to_rc.py` 的
    `PROJECT_BLOCK` 模板也补上 `PROJECT_TAG`，避免哪次重注入把标识弄丢。
  - `runtime/bridge/VERSION` 停在 `1.1.0`（源码已是 `1.2.9`），已同步。

## 消息发不出去 / 气泡异常 / 群友被叫错名（2026-09-18）

主题：**把"用户报障 → 查日志 → 定位真因"这条链走完，修掉 4 个真 bug**。
起因是用户报「消息没发出去，最后自己手动补发」+「bot 老把『群友C』叫成
『群友C』」，顺带全量复查了日志。

### 修复

- **引用回复「发了但没发出去」——最严重的一个（用户报障的直接原因）**
  现象：用户报「群友B博士早呀～海猫小故事…」那条没发出去，是自己手动补发的。
  日志里那条却打着 `[UIA✓] 引用 → …`，桥接认为成功、不做任何重试。
  真因：`uia_sender.py` 的原生引用分支调的是
  `self._send_current(ctrl, verify=False)`。`verify` 的语义是"要不要用
  「输入框是否已清空」判断成败" —— 传 `False` 是给**发图片/文件**用的
  （那时输入框里没有文本，判据不成立）。但引用发送的输入框里**明明有正文**，
  传 `False` 会让 `_send_current` 在点完发送按钮后**直接 `return True`**，
  完全不校验有没有真发出去。
  代码注释里还留着线索：早年有个"空引用块残留"的 bug，导致清空判据永远失败，
  当时把调用改成 `verify=False` 当作绕过；后来残留问题用
  Ctrl+A+Delete 真正修好了（见 `clear_input`），但这个 `verify=False` 忘了改回来。
  修法：改回 `verify=True`；失败时照常打 `[UIA✗]` 并**降级普通发送**，
  于是"发失败"不再静默。
- **群友被叫错名字（用户报障）**：名册里真名是「群友C」，
  模型会把它简体化成「群友C」。出站纠错表 `_JA_TO_CN_VARIANT` 是**手写**的，
  有「広→广」却**没有「緒→绪」** ⇒ 生成的变体是「群友C」，
  与模型实际输出「群友C」不相等 ⇒ **一次都没匹配上**
  （日志证据：错名出现 11 次，`昵称纠错` 计数 0）。
  修法两层：
  ① 补齐变体表（`緒→绪` 及一批常见繁/日→简字形）；
  ② 新增 `_build_fuzzy_name_map()`「逐位兜底」—— 对每个名字额外登记
     "只改其中一位"的变体，这样模型只简体化其中几个字时也能认出；
     以后再漏字也只是匹配面变窄，不会整条失效。
  实测四种写法（全简/半简/混用）都能纠正回「群友C」，
  而「广东」「车站」「关系」「陆续」等普通词不受影响。
- **微信气泡顶上多一个空行**：AstrBot 分条回复时先发一个 `" "` 段、
  再发 `"\n正文"` 段（日志原文：
  `chain=[{reply},{at},{text:" "},{text:"\n…"}]`）。
  桥接本来就跳过了纯空白段（对），但**没有去掉正文的前导换行**，
  于是微信里就是一个空的首行 —— 最近一次运行实测 8 条。
  修法：正文做一次 `strip()`（中间的换行与缩进保持原样）。
- **面板改设置「保存成功」但其实没存进去**：日志出现过
  `[Web] 保存配置失败: Extra data: line 35 column 2`。
  真因：`/mode`（切群聊模式）与 `/api/config` 都是
  「读 → 就地改写 → 直接 `json.dump` 到原文件」。面板被连点两下
  （或开了两个标签页）时两次保存并发，后一次的写入落在已写一半的文件上，
  拼接出两份 JSON。现场残骸 `config.json.bak_broken_201419` 还在。
  修法：新增 `_atomic_write_json()`（先写临时文件 + `fsync` + `os.replace`），
  两条保存路径都改走它；另加 `_read_config()`，文件真损坏时自动回退到
  最近一个可用备份，避免面板彻底卡死。

### 其他

- 复查结论（**不是** bug，说明一下免得后人重复排查）：
  - `⚠️ 无 AstrBot 客户端在线`（16 次）都发生在 AstrBot 进程重启期间，
    消息是**缓存等重连**，不是静默丢弃。
  - `[UIA✗] …内容已填入输入框但未能发出`（1 次）是**正常报错**——
    正是这条路径在正确地发现问题（与上面第 1 条形成对比：引用那条不会报）。
  - 单条 `Error in ASGI Framework / WinError 121` 是一次网络超时，非系统性。
- 复盘教训：**改运行副本 `runtime/bridge/` 再 `sync_to_rc.py` 同步到
  `wechat-weflow-bridge-ob11/`**——反着来会把改动覆盖掉（本次踩过一次）。

## 发行体系重构：废弃便携版，改为「正式发行版」（2026-09-18）

主题：**把"给别人用的包"从"什么都塞"改成"只放跑得起来的东西 + 安装包"**。

### 变更

- **删除便携版体系**：`scripts/build_portable.py`、`release/portable/`、
  `scripts/portable_readme.md` 全部移除。**以后不再做便携版。**
  它的毛病是定位不清：既想当运行包，又把项目文档、模拟器、维护脚本一股脑塞进去，
  包又大又杂，收件人根本用不上；而且归档里还带着运行数据。
- **新增正式发行版构建器 `scripts/build_dist.py`** → `release/dist/Akasha-WeChat-vX.Y.Z.zip`。
  包内只有：`akasha/`（桥接完整副本）、`astrbot/`（AstrBot 完整副本，含框架与依赖）、
  `python/`（免安装基座）、`installers/`（安装包）、启动器与使用说明。
- **发行版改为放「安装包」而不是「程序本体」**：WeFlow 与微信都只放安装包
  （`installers/`），由收件人自己安装。以前把 WeFlow 程序本体（701MB）直接拷进去，
  既是未授权再分发，也让包无谓地大。
  收件人放安装包的位置：项目根或 `scripts/` 下的 `installers_src/`，
  构建时按文件名关键字自动归类；**找不到只告警不中止**（微信旧版安装包腾讯已下架）。
- **源码归档（`build_release.py`）瘦身**：`versions/` 与 `newestbuild/` 里
  **除源码外只放安装包**，不再堆其他东西；同时移除了 `--zip`「纯净版」产物
  （与发行版职责重叠，已无必要）。
- **新增相对路径启动脚本**：发行版根目录的 `启动 Akasha.bat` / `停止 Akasha.bat`
  用 `%~dp0` 定位自身，解压到任意目录都能跑；`astrbot/` 内另给一份
  `启动 AstrBot.bat`，只拉起 AstrBot 自己（单独调试用），
  基座 Python 找不到时还能回落到 PATH 里的 python。

### 修复

- **API Key 藏在 `custom_headers` 里，脱敏漏掉（严重）**：AstrBot 的
  `cmd_config.json` → `provider_sources[*].custom_headers.Authorization`
  会写成 `"Bearer sk-cp-..."`（MiniMax 那类服务就是这么配的）。
  旧的脱敏只清 `key` / `api_key` / `embedding_api_key`，
  **这条完整可用的 Key 会原样进包**。实测本机 5 个 Key 都受影响。
  修法：
  - 对 `custom_headers` 做「敏感头名」扫描（auth/key/token/secret/cookie/
    credential/password/session），命中即清空 —— 不再逐个字段硬编码；
  - 对 provider 的每个字符串字段加一道「长得像密钥就清掉」的兜底；
  - 全包加**密钥兜底扫描**：不看字段名、只看内容特征
    （`sk-…` / `nvapi-…` / `AIza…` / `ghp_…` / `hf_…` / `glpat-…` / `Bearer …`），
    命中即中止出包。
    第一版扫描器把 `sk_` 当特征，结果误报 782 处（`sk_feed`、`task_id`、
    SPDX 的 `sk-exception` 全是假阳性）—— 已收紧为「前缀 + 长度 ≥32 +
    同时含字母与数字 + 排除占位符」，并只在**我们自己的文件**里扫，
    不扫第三方 venv。
- **venv 里写死的本机绝对路径 / Windows 用户名**：`pyvenv.cfg`、
  `Scripts/activate*`、`Scripts/*.py` 共 24 个文件带着
  `C:\Users\<用户名>\...`。基于"运行数据标识符"的脱敏表覆盖不到本机路径
  （表是从 wxid/群名生成的），是靠新加的**硬检查**才拦下来的。
  修法：构建时把两个 venv 的 `pyvenv.cfg` 重写为占位 `home`
  （启动器本来每次启动就会用实际路径重写它，不影响运行）、
  `activate*` 里的路径做文本替换、删掉遗留的 `pyvenv.cfg.bak_*`。
- **`build_release.py` 归档里带着真实隐私**：源码 / 文档 / 脚本本来就有
  真实 wxid、群名、人名、本机路径（开发环境是有意保留的），
  但归档出去同样不该留着。现在归档后会自动跑一遍脱敏。
- **`build_release.py` 在 GBK 控制台下崩溃**：输出 `✅` 直接抛
  `UnicodeEncodeError`。已加 stdout UTF-8 重配置。
- **`release/*/_runtime-data-snapshot/` 隐私泄露**：该目录拷的是
  `runtime/bridge/data/*.json`，里面是真实 `persons.json`（人员名册）、
  `chat_names.json`（真实会话名 + wxid）、`admins.json`。
  这直接违反"封装出的 release 绝不能有隐私"，**已从归档中彻底移除**，
  并在脚本注释与 `AGENT.md` 里立了红线。

### 隐私边界（明确下来）

| 保留 ✅ | 删除 ❌ |
|---|---|
| **三个人格**（`data_v4.db` 的 `personas` 表）—— 软件资产，可开源 | 全部 API Key / 面板口令 / jwt_secret |
| **普通知识库文档**（`astrbot/kb_docs/*.md`） | **向量知识库**（`knowledge_base/*/{doc.db,index.faiss}`） |
| AstrBot 框架与依赖 | 聊天历史 / 会话映射 / 定时任务 / 好友群名单 / 桥接 `data/` |

出包前跑两道闸门：`sanitize_privacy.py` 全包审计 + 「本机用户名 / 绝对路径」硬检查，
**任一有残留就中止出包**。

### 其他

- 文档同步：`AGENT.md` §5/§6、`docs/依赖与目录说明.md` §4/§5、
  `README.md` 的目录结构与「版本与出包」小节。

## 便携版（免安装打包）—— 随 v1.2.9 一起发布

主题：**让"换台电脑"这件事从"装一整天环境"变成"解压 + 双击"**。

### 开发环境改为自包含（2026-09-17）

- 新增 **`vendor/`**：把外部依赖收进开发文件夹 —— `vendor/python/`（基座解释器，
  两个 venv 的 `pyvenv.cfg` 都指向它）与 `vendor/weflow/`（WeFlow 程序本体）。
  以前这两个都在系统别处（WorkBuddy 自带环境 / `%LOCALAPPDATA%`），
  换机器就起不来，也说不清到底依赖了什么。
- 新增 **`docs/依赖与目录说明.md`**：逐项列清楚"什么在文件夹里、什么在外部、为什么"，
  以及开发环境与便携版的区别、换电脑怎么办。
- ⚠️ **未变的前提**：微信（腾讯的软件，必须装+登录）与 Ollama（可选）仍在外部；
  `%APPDATA%\WeFlow`（含微信数据库解密密钥）**永远不能拷进来**。

### 隐私修复（2026-09-17 复查时发现）

- **本机路径泄露**：便携版里 18 个文件带着 `C:\Users\<用户名>\...`（venv 的
  `pyvenv.cfg`、`activate*`、部分脚本、架构图 json）。已把本机路径加入脱敏表；
  并在 zip 直写时做**字节级替换**（纯 ASCII 模式，不受 GBK/UTF-8 混编影响）。
- **新增成品包校验**：`build_portable.py` 打完 zip 会对**成品本体**再扫一遍
  （staging 审计覆盖不到"直接写进 zip 的大目录"）。分两档：
  - **hard**（wxid / 群ID / 本机路径 / 用户名）→ **全包检查**
  - **soft**（中文昵称）→ 只查我们自己的文件
    （第三方词典与 LICENSE 里本来就全是常见词：jieba 词典有"妈妈/爸爸/家人"，
    LICENSE/AUTHORS 有 Charlie/群友I 这类常见英文名 —— 那是误报，不是隐私）
- **不再自动替换常见英文名**：实测会大量命中第三方库的 LICENSE/AUTHORS，误报率极高
  且几乎没有识别性；真正要处理的英文标识（`测试用户`、`RulerCordelius`）手动列白名单。
- 随包 `tools/` **不再带构建期工具**（`build_portable.py` / `sanitize_privacy.py`）：
  它们内部必然写着扫描模式（含真实标识符），收件人也用不上。

### 新增

- **`scripts/build_portable.py`**：一条命令产出完整便携版
  （`release/portable/Akasha-WeChat_便携版-vX.Y.Z.zip`）。包里自带：
  - 免安装 Python 运行时（基座解释器，约 53 MB）
  - **AstrBot 及其全部依赖**（连它自己的 venv 一起，免 pip）
  - **桥接及其全部依赖**（同上）
  - **WeFlow 程序本体**（Electron，直接拷即可运行）
  - 角色人设、知识库、对话模拟器、维护脚本、项目文档

  **venv 可移植的原理**：Windows 的 venv 靠 `pyvenv.cfg` 里的 `home` 定位基座解释器。
  启动器在每次启动时把「包内 python 的当前绝对路径」写回该文件，venv 就能在任何路径下运行
  （已实测：换目录后依赖全部正常导入）。

- **`启动 Akasha.bat`**：一键启动 —— 校正环境路径 → 检查首次配置 → 依次拉起
  WeFlow / AstrBot / 桥接（自动等端口就绪）→ 自动打开控制面板。
- **`停止 Akasha.bat`**：按端口一次性停掉 AstrBot 与桥接，并清理 `bridge.pid`。
- **`① 首次配置.bat` + `scripts/firstrun_config.py`**：交互式向导
  - WeFlow Token：**优先自动从 `%APPDATA%\WeFlow\WeFlow-config.json` 读取**，读不到才让手填
  - 机器人微信昵称 / wxid
  - 对话模型：内置 DeepSeek / Kimi / 硅基流动 / 通义 / OpenRouter / 自定义 六种预设，
    写入 AstrBot 的 provider 配置并设 `max_context_tokens=65536`
  - 完成后写 `.first_run_done` 标记，启动脚本据此判断是否已配置
- **`scripts/sanitize_privacy.py`**：隐私脱敏工具（审计 + 替换，可复用）
- **`scripts/check_patches.py`**：一条命令总检六项核心补丁是否还在
- **`使用说明.md`**（随包）：从零上手、常见问题、隐私说明

### 隐私（重要）

便携版**不含任何个人数据**，构建时强制校验：

| 处理 | 内容 |
|---|---|
| 剥离 | 全部 API Key、AstrBot 面板口令 / `pbkdf2_password` / `jwt_secret` |
| 清空 | `data_v4.db` 只留 personas 表；聊天历史、会话映射、定时任务、API Key 全清 |
| 不带 | 桥接 `data/`（含真实 wxid / 群名 / 人名）；AstrBot 的 `backup/` `logs/` `*.bak_*` |
| 绝不拷 | **WeFlow 的用户数据目录 `%APPDATA%\WeFlow`**（那里有微信数据库解密密钥） |
| 脱敏 | 文档、变更日志、源码注释里的真实 wxid / 群 ID / 群名 / 人名 → 占位符 |

构建流程最后一步会对整包跑一遍脱敏审计，**有残留就中止出包**。

### 说明

- 收件人仍需自行准备：**微信桌面版（安装并登录）** 和 **一个模型 API Key** ——
  前者是腾讯的软件无法随包分发，后者属于个人凭据不能打包。
- ⚠️ **WeFlow 是第三方程序**：其源码仓库已因腾讯 DMCA 投诉下架，且未附任何开源许可证。
  按用户要求内置以便"解压即用"，**请勿公开再分发本包**。
- 构建目录默认用短路径 `C:\_akasha_build`：venv 有近 5 万个小文件，放在深目录会撞
  Windows 260 字符路径上限；产物再打成 zip 放进 `release/portable/`。

## [1.2.9]

这一版的主题：**把"伪装成记忆"的知识库措辞改回"如实说明是知识库"，根治"雷霆大回忆"**。

### 修复（严重）

- **模型开始编造亲身经历**（用户称之为"雷霆大回忆"）：
  > 我又想起好多罗德岛的事：星极的球仪还在角落转，海霓总盯着天上像在看海浪流动……

  根因是两句话叠加：
  1. 注入模板（`kb_mgr.format_context`）写着「你想起来的记忆，**请像亲身经历一样自然地使用**」；
  2. 人设里写着「被问『你怎么知道的』→ 说成自己的记忆或见闻（"我记得呀"）」。

  于是资料被当成"自己的回忆"讲出来，还会配上人名编往事。
  这是 2026-09-13 那版"防穿帮补丁"**矫枉过正**的结果 —— 当时为了避免说漏"知识库"，
  把措辞整个改成了"记忆"。

### 变更

- **知识库措辞改回如实标注**（`scripts/patch_kb_wording.py`，改 3 个 AstrBot 文件共 4 处）：
  注入头/模板改为「以下是【知识库】检索到的资料，作为你回答时的事实依据」，并给三条要求：
  ① 当客观资料用，不要说成自己的亲身经历、回忆或见闻；
  ② 正常回复里不要出现"知识库 / 资料库 / 检索 / 文档"这类字眼；
  ③ **只有当用户主动问起资料来源时，才可以如实说明**。
- 工具 description 由 `Recall your own long-term memories… use it like thinking back` 改为
  `Look up your knowledge base…（treat as OBJECTIVE REFERENCE MATERIAL, never as your own
  memories）`；空结果文案由"（你想了想，没有想起…）"改为"（知识库里没有检索到…不要编造）"。
- **人设三条规则**（`scripts/patch_persona_kb_framing.py`，带备份 / `--revert` / `--verify`）：
  - 「你怎么知道的」那条删掉"说成自己的记忆或见闻"，改为"不许把资料编成亲身往事"；
  - 「绝不暴露」段补**例外**：被直接点名问到时如实承认，不装傻、不生硬回避；
  - 「话题边界」禁令扩写到"禁止用（悄悄说…）等方式把资料包装成回忆；
    资料是设定资料、不是你亲历的过去"。

### 验证（走模拟器，不打扰真实会话；`scripts/probe_kb_wording.py`）

| 场景 | 结果 |
|---|---|
| 问「星极是谁呀？」 | 客观事实（星占师 / 莱茵生命顾问 / 妹妹星源…），**无"我又想起"** ✅ |
| 问「你怎么知道这些的呀？」 | "我记得的呀，平时看资料的时候留了心的喵" —— 无编造 ✅ |
| **直接点名**问「是不是有知识库／资料库」 | "博士这么直接问的话，我得老实说喵。我确实有些可以参考的资料…" —— **如实承认，不硬躲** ✅ |

## [1.2.8]

这一版的主题：**发送链路的四个真 bug（顺序颠倒 / 空引用气泡 / 路由空异常 / 文件发不出去）**。

### 修复（严重）

- **消息顺序会颠倒**（用户报"同一件事颠三倒四说了两三遍"）。
  根因：`ob_client.py` 用 `asyncio.create_task` **并发**处理 AstrBot 的 API 请求，
  而 AstrBot 的「分条回复」是按顺序逐条 `await event.send()` 发的 —— 桥接这边并发处理
  会让多条 UIA 发送互相竞争，落屏顺序随机（实测：开头那句被挪到了最后）。
  **改为单 worker 队列串行消费**：到达顺序 == 发送顺序。副效果是 AstrBot 必须等前一条
  回响应才发下一条，**乱序在结构上不再可能**（实测 19:52 两次发送间隔 4 秒，就是它在等）。
- **空引用气泡 / 消息卡在输入框**。根因：微信输入框里的「引用节点」是富文本对象，
  `ValuePattern.SetValue("")` **删不掉**（读回来是空串，界面上仍留一个空引用块）。
  残留引出两个历史疑难：① 后续发送夹带垃圾 → 群里出现**空的引用气泡**；
  ② `_send_current` 用"输入框是否为空"判成败会永远失败，媒体发送被迫改成
  `verify=False`（点一下按钮就算成功）→ **"发了没发"完全不可知**（就是"卡在输入框"）。
  新增 `UiaSender.clear_input()`（Ctrl+A + Delete 真删，幂等），并在
  `send_text / send_quote / send_image / send_file` 发送前调用；
  媒体发送的校验改回 `verify=True`，失败时也清一次，不留残留。
- **图片/文件永远发不出去**。根因：剪贴板走 `subprocess.run(["powershell", ...])` 调
  WinForms，在受限环境（自动化工具/沙箱启动的进程）里**调用被拦截**，稳定卡 30 秒后失败。
  改成 **ctypes 直写 Win32 剪贴板**（CF_HDROP ≈ 4ms、CF_DIB ≈ 0.3s），不再依赖任何子进程。
  ⚠️ 64 位下必须显式声明 `argtypes/restype`，否则句柄被截断成 32 位、`GlobalLock` 返回 NULL。
- **定时任务发送路由兜底不完整**（AstrBot 侧补丁）。原来写成 `elif`（只在"多客户端"时
  生效）；而 `event_ws` 指向已失效连接、或显式传的 `self_id` 查不到时，`api_ws` 会保持
  None 并抛**空异常** → 同一年同一秒内出现"一条成功、两条失败"。
  改为独立的 `if`：**任何分支落空都兜底**（排除模拟器后仅剩一个客户端才用）。

### 新增

- `uia_sender.clear_input()`：可靠清空输入框（含富文本引用节点），已进 AGENT.md 铁律。
- 桥接出站新增**原始消息链日志**：`[OB11] ← {action} target=… chain=[…]`，
  分条/引用/顺序类问题靠它定位（正文可能含换行，解析务必先合并续行）。
- `state.get_contact` 增加**通用反查**：任何已知会话名（含「文件传输助手」这类非联系人）
  都能由整数 ID 还原真名，不再退化成裸 ID 去搜索。
- `scripts/shot_wechat.py`：微信窗口截图工具（人工确认发送结果，可 `--right` 只截聊天区）。
- `scripts/test_send_media.py`：媒体外发实测（文件 + 图片，目标固定为「文件传输助手」）。
- `scripts/test_ob_segments.py`：出站分段回归 10 项（空白段/引用合并/@合并/顺序/图片/文件）。
- `patch_aiocqhttp_primary_client.py` 支持 `--selftest`（还原→重打，逐字节比对等价）。

### 验证（端到端，实测通过）

- **媒体外发**：SVG 文件 + PNG 图片成功落到「文件传输助手」（WeFlow 确认 `isSend=1`）。
- **定时任务**：一次性 cron（目标=文件传输助手）→ agent 用 `astrbot_file_write_tool`
  画 SVG → `send_message_to_user`(plain + file) → `Message sent to session …161333918`
  → 桥接 `[UIA✓] 文件 → 文件传输助手: mon3tr_test.svg`；WeFlow 确认收到且**顺序正确**
  （19:52:23 文字 → 19:52:28 文件）。
- 遗留：**群里的多段回复顺序**需要等下一次真实群消息才能用新的 `chain=` 日志复核。

## [1.2.7]

这一版的主题：**修掉基础设置页开关的显示错乱**（点过开关才会出现，所以很容易漏）。

### 修复

- **开关的「开/关」文字跑进滑块里，被圆点遮住一半**。
  现象：点过某个开关后，滑块内部多出一个半个字，右边那两个字还停在点击前的状态。
  根因是 v1.2.3 重构时 `onchange` 用了 `querySelector('span:last-child')` 来定位文字，
  而这个选择器会**先命中 `.switch` 内部的滑块 `<span class="sl">`**
  （它是 `.switch` 的最后一个子元素），于是 `textContent` 被写进了滑块本身。
  改为给文字加 `class="st"` + 独立的 `syncSwitchText(this)` 函数；
  顺带把 `onchange` 里那串嵌套引号去掉，避免转义踩坑。
- **开关里的隐藏 checkbox 会被表单样式撑大**：`.settings-field input` 的
  `padding:8px 11px` / `border:1.5px` 也作用到了 `.switch input` 上，
  使这个本该 0 尺寸的元素变成约 25×19 的透明块（会占位、影响标签点击区）。
  已在 `.switch input` 显式清掉 `padding/border/margin/background` 并加 `appearance:none`。

### 新增

- `scripts/verify_switch_fix.py`：用面板**真实的 `<style>`** 生成最小复现页，
  把「旧写法 / 新写法」并排渲染并自动点击，交给 Edge 无头截图对比。
  旧写法的截图与用户反馈完全一致，新写法干净 —— 这类「点击后才出现」的
  UI 问题靠静态截图是发现不了的，留个可复跑的回归工具。

### 验证记录（2026-09-16 00:22）

**「定时任务发错会话」的修复（1.2.6）已通过真实链路端到端验证。**

- 方法：把微信先停到「文件传输助手」当诱饵，再用 `--clone` 复用线上任务的指令插入一条
  一次性 cron 任务（目标＝博士私聊），重启 AstrBot 等它自然触发。
- 结果：
  - AstrBot：`Tool 'send_message_to_user' Result: Message sent to session wechat_bridge:FriendMessage:1000000001`
  - 桥接：`已切到会话: RulerCordelius（列表匹配，等级 3）` → `[UIA✓] 文字已发送至 RulerCordelius`
  - WeFlow：消息落在**私聊**（00:22:11），**诱饵会话没有**收到 —— 正是修复前会发错的地方
- 附带查清两件事（详见 `docs/开发文档.md` §4.9.1 / §4.9.2）：
  1. 自检指令若写成「系统指令式」会被 AstrBot 的 `safety_mode` 判为提示词注入而拒答，
     或**谎报成功**（回了"已处理完成"却没调用发送工具）→ 自检一律 `--clone` 真实指令。
  2. `data/logs/astrbot.log` 启动后即停写、stdout 又块缓冲 → 排障要用
     `PYTHONUNBUFFERED=1 ... -u run_astrbot.py run` 启动。
- 新增工具：`scripts/park_wechat.py`（把微信停到诱饵会话）、`scripts/dump_conv.py`
  （看 agent 到底回了什么）、`scripts/clean_test_artifacts.py`（清自检留下的 cron 任务与
  对话历史垃圾，会先备份）。

## [1.2.6]

这一版的主题：**原生引用打通 + 定时任务发错会话根治 + 知识库接线**。

### 修复（严重）

- **定时任务/主动发送把消息发到了「当时打开的会话」**。9/15 21:30 两条定时消息
  （群晚安 + 私聊催睡）**全掉进了「文件传输助手」**，目标会话都没收到，
  而桥接日志却写着"已切到联系人 / 文字已发送至 1000000001"。
  三处叠加：
  1. `uia_sender.py` 里切不到目标会话时**故意**"尝试在当前窗口发送"→ 发错人；
  2. `state.get_contact()` 的直连映射表 `_ob_id_to_contact` 是空的，
     于是拿**原始数字 ID** 当联系人名去找会话，必然找不到；
  3. 补上反查后又暴露：私聊**聊天标题显示的是备注名**（RulerCordelius），
     而名册里 `names[0]` 是昵称（测试用户）→ 搜索切到 测试用户、标题却是
     RulerCordelius → 校验失败。
  修法：
  - ⚠️ **安全红线：切不到目标会话就放弃这次发送**，绝不发到当前窗口；
    切完还会再校验一次当前标题，不一致也放弃（日志打 `[UIA✗]`）。
  - `get_contact()` 增加**反查**：ob_id → 群（反查 `known_groups`）→ 人
    （`all_persons()[wxid].uid`），且人**优先用 `get_chat_name(wxid)`**
    （WeFlow contacts 的 displayName = 备注名 = 聊天标题）。
  - 回归脚本 `scripts/test_session_switch.py`：先把微信停在「文件传输助手」，
    再发到私聊 → 实测通过，WeFlow 确认落到正确会话。

### 修复（功能）

- **原生引用终于可用**。此前三次探测的结论"微信右键菜单 UIA 看不见"是**错的**，
  真因两个：
  1. `item.RightClick()` 点的是**整行中心**，那里是空白、菜单不弹；
     要点在**气泡**上（自己发的消息靠右，实测 x≈62% 命中）。
  2. 菜单**既不是新顶层窗口、也不是 Win32 的 `#32768`**，而是**微信主窗口的子节点**
     （路径 `/Weixin/引用`，`MenuItemControl`）；之前只找"新增顶层窗口"所以永远找不到。
  已实现 `_right_click_until_menu()`：横向扫描 6 个位置，每点一次用
  `_find_quote_menu()` 查找，判据是**同名 MenuItemControl 且父控件里有
  「复制/转发/删除」兄弟项**（避免把常驻同名控件误判成菜单）。
  参考 Mon3trBot v1.7.4 的 `send_quote()`（其关键点是引用前先 `roll_into_view()`）。

### 变更

- **知识库接线**：`arknights` 库其实早已导全（32 个文档 / 12326 分块，
  Mon3trBot 的方舟资料全在里面），但 `cmd_config.json` 的 `kb_names` 是**空的**，
  等于没接。已设为 `["arknights", "endfield"]`（知识库是自动注入的，
  见 `astr_main_agent.py`）。实测矿石病致死率、325 梗均可正确回答。

### 新增

- `docs/测试题库.md`：110 道题的回归题库（常识 / 方舟知识库内 / 方舟游戏本体 / 人设特化），
  每题带判定关键词与禁止词，文末写明判分规则与待复核项。
- `sim/qa_suite.py`：读该题库自动出题、通过模拟器跑、分组统计、输出 JSON 报告。
- `scripts/probe_quote5.py`：引用探测（`--sweep` 横向扫描 / `--do` 真发 / `--seed` 播种）。
- `scripts/clear_input.py`：清空某会话的聊天输入框（探测残留文字用）。
- `scripts/test_session_switch.py`：会话切换 + 发送的回归测试。

## [1.2.5]

这一版的主题：**修掉机器人把群友「群友C」叫成「群友C」的问题**。

### 修复

- **模型把日语汉字自动简体化，导致叫错群友名字**。
  查日志确认：收信侧 127 次全是正确写法「広」，18 处错误**全部出现在机器人发出的回复里**
  —— 是模型自己把「広」写成了「广」。两层一起修：
  1. `scripts/patch_persona_name_rule.py`：人设加「名字照抄」死命令
     （群友昵称一个字不许改，特别点名 広/沢/気 这类日语汉字；群名同理）。
     带备份与 `--revert`。
  2. `ob_protocol.fix_display_names()`：出站前用工整的名册再兜一道。
     **安全边界**——只有当"被简体化后的写法"能唯一对应到一个**已知名字**时才替换
     （用 196 个已知展示名建变体表，当前命中 1 条：群友C → 群友C）。
     所以"广东""车站"这类普通文字完全不受影响；命中时打日志
     `[OB11] 昵称纠错：… → …` 方便核对。
  3. 顺带新增 `state.known_display_names()`：汇总人名 / 群成员名 / 群名，供纠错使用。

## [1.2.4]

这一版的主题：**修复面板保存写坏 config.json + 机器人身份自动获取**。

### 修复（严重）

- **面板「保存配置」会把 config.json 写坏**：写入末尾多了一个字面量 `\n`（两个字符），
  之后 config.json 无法再被解析，桥接重启会直接崩、设置页也会提示"加载配置失败"。
  根因是 v1.2.3 重构面板时把 Python 的 `"\n"` 误写成了 `"\\n"`（共 3 处：
  两处写文件、一处日志拼接）。已全部改正，并修复了已损坏的 config.json
  （29 个键值完整保留，坏文件备份为 `config.json.bak_broken_*`）。

### 新增

- **机器人身份自动获取**（基础设置 → 机器人身份 →「🔍 从微信自动获取」）：
  - wxid：从 WeFlow `/api/v1/messages` 里找 `isSend=1` 的消息，`senderUsername`
    就是本机账号（最权威的来源，因为那条消息就是这台机器发出去的）。
    wxid 已填时不覆盖，只在为空时自动填入。
  - 昵称：从各群 `/api/v1/group-members` 里按 wxid 找到自己的条目，
    收集 displayName / nickname / 群昵称 / 备注。手动改过就不覆盖，点按钮才刷新。
  - 实测能识别出 wxid 与 `Mon3tr`。

### 修复（其他）

- **wxid 比对容错**（`bridge_core.ignore_reason`）：微信 4.x 有时给 wxid 带 `_xxxx` 后缀，
  本机配置是 `wxid_rvph2xhviigs19_79c1` 而 WeFlow 报的是 `wxid_rvph2xhviigs19`，
  原来的 `==` 比对永远不命中，"跳过机器人本机消息"这条保险失效
  （目前靠昵称兜底才没出事）。改成前缀互比，两个方向都能命中。

## [1.2.3]

这一版的主题：**Web 面板第 2/3 页重构 —— 更好看、更方便、把说不清的说清**。

### 变更

**基础设置页**
- 全部设置项分成三层：**常用**（机器人身份 / 消息行为 / 图片，常驻展开）、
  **进阶**（连接地址 / 端口 / 日志，折叠）、**上游遗留**（桥接侧图片转述等 9 项，折叠并标黄警示）。
  没有任何配置被删除（遵守「不得删除上游既有代码」），只是不再占着主视野。
- 新增**搜索框**：输入关键字即时过滤（如「图片」「端口」「token」），命中时自动展开折叠层。
- 布尔配置从下拉框改成**开关**；会改了要重启的字段加「需重启」角标（共 5 个）。
- 补上两个一直没暴露的配置：`mention_as_text`（@ 转文字，默认开）、
  `quote_reply_native`（原生引用，当前微信不可用，默认关）。
- 把「实测不可用」的选项标清楚：`send_method=weflow_api` 标注"必然发不出去"；
  `weflow_send_api` 标注"当前代码没有使用这个配置"。
- 保存条改为吸底常驻，并写明生效方式（群聊模式立即生效，其余需重启桥接）。

**成员与权限页**
- **新增「群里管什么」总表**：每个群一行，两列开关——
  **回复**（要不要理这个群，立即生效）+ **插嘴**（没人 @ 时会不会自己冒出来）。
  原先散在三处的「群回复开关 / 插话黑名单」收进这一张表。
- 插话黑名单改为**反向表达**：表格里勾 = 允许插嘴，不勾 = 进黑名单；
  不在已知群列表里的旧条目仍保留在「高级」区的手动补充框，不会丢。
- 当**插话白名单非空**时自动显示黄色警示（此时表格的勾选会被白名单收紧），
  避免出现"明明勾了为什么还不插嘴"的困惑。
- 重复的三段「白名单其他自定义条目」说明合并为一个「高级」折叠区，
  三层过滤关系（平台白名单 > 群回复开关 > 插话白/黑名单）用一段话讲清楚。
- 155 人的成员表改为**内部滚动**（表头吸顶），不再把下面的内容顶出两屏。
- 管理员立即生效、白名单/插话需重启 AstrBot，在保存条上写明。

### 新增

- 面板支持 **hash 深链**（`#settings` / `#members`）：刷新后停留在原页签。

### 修复

- 上游遗留的 `ollama_*` / `image_caption_*` 字段此前在表单里裸露，容易被误改；现折叠收起。

## [1.2.2]

这一版的主题：**定时任务静默失败根治 + 人设话题边界**。

### 修复（严重）

- **定时任务 / 所有主动发送 100% 静默失败**。用户在群里问「为什么定时任务没按时触发」。
  实测：任务**准时触发了**（`cron_jobs.last_run_at` 正常跳），失败在发送环节。
  根因是 `aiocqhttp.WebSocketReverseApi.call_action`：主动发送（无事件上下文）
  只能靠 `len(_api_clients) == 1` 选路由，而本机同时挂着**模拟器**
  （`sim/sim_wechat.py`，`X-Self-ID=99009900`）→ 抛 `ApiNotAvailable`。
  该异常不带参数、`str(e)` 为空，所以 AstrBot 侧只看到
  `error: failed to send message to session xxx: `（冒号后空白），
  DB 里却仍写 `completed` / `last_error=None` —— **悄无声息**。
  实测 2026-09-14 当天 **7 次调用 0 次成功**（含 6:00 早安天气、21:30 催睡群/私聊）。
  修复：`scripts/patch_aiocqhttp_primary_client.py`，多客户端时排除模拟器，
  剩余候选不唯一时仍拒绝（绝不猜）。回归测试 `scripts/test_aiocqhttp_routing.py`。
  **端到端验证通过**：23:16:00 的一次性 cron 实测
  `Tool send_message_to_user Result: Message sent to session ...`，
  桥接侧 `[UIA✓] … 文字已发送至 1000000001`，且模拟器仍在连接状态。

### 新增

- `scripts/cron_test_push.py`：主动发送链路自检工具。
  `--clone <任务ID>` 可复用真实任务的指令做高保真自检，`--cleanup` 清理。
- `scripts/test_aiocqhttp_routing.py`：补丁的回归测试（4 个场景，含事故场景）。
- `scripts/patch_persona_topic_guard.py`：给 mon3tr 人设加「话题边界」段落
  （可 `--revert`，原人设备份到 `data/backup/`）。

### 修复（其他）

- **人设无端倒游戏剧情**：bot 连续多轮主动大段复述《明日方舟》剧情
  （「我又想起好多罗德岛的事……」），并把群友的**现实**项目与游戏设定混为一谈，
  甚至编造出历史里根本不存在的人名（"杏仁"）与往事（全库检索 0 命中）。
  上下文只有 3.5 万 token，**不是上下文爆炸**，而是自我复述形成的正反馈循环
  （它自己的长输出进了历史，下一轮接着往下编）。已给人设加「话题边界」段落。

### 文档

- `docs/开发文档.md` §4.9：补全定时任务的执行链路（消息只能靠 agent 调工具发出）、
  「aiocqhttp 只能挂 1 个 OneBot 客户端」铁律、以及自检方法。
- `docs/开发文档.md` §6：补丁清单新增 `aiocqhttp/api_impl.py`。
- `AGENT.md`：已知坑新增上述铁律。

## [1.2.1]

这一版的主题：**上下文爆炸治理 + 出站段（引用/@）修复**。

> v1.2.0 是本地中间构建、未对外发布，本版包含其全部改动。

### 修复（严重）

- **UIA 发送器死锁**：`_lock` 用了不可重入的 `threading.Lock`，而 `send_quote` 会在
  持锁状态下调用 `send_text` 降级发送 → 第二次 acquire **永久自锁**，实测卡死发送线程
  80s+ 不返回。生产影响：AstrBot 每发一条带 `reply` 段的回复都会卡死桥接发送线程。
  已改为 `threading.RLock`。
- **上下文无限膨胀**：`/stats` 实测单会话达 **1,224,323 tokens**。根因是
  `agent_runner.config.compression.max_turns = -1`（永不按轮数截断）。治理方案见「变更」。
- **主动回复概率被还原**：`possibility_reply` 从 0.1 改回 **0.03**（此前改过又被覆盖）。
- **AstrBot 面板看不到黑名单**：此前只加了默认值与类型 schema，漏了 WebUI 提示区
  （`CONFIG_METADATA_3`）。已补 `provider_ltm_settings.active_reply.blacklist`。
- **`at` 段被静默丢弃**：出站只处理 `reply/text/image/file/face`，`at` 不在其中 ——
  所以群里的回复看不出在回谁。

### 变更

- **上下文治理改为 token 阈值优先**（原为轮数硬截断）：所有文本对话模型的
  `max_context_tokens` 设为 **65536**，超阈值走 `llm_compress` 把旧对话**总结成摘要**保留；
  `max_turns` 放宽到 **100** 只作兜底。理由：轮数截断是硬丢弃会真的忘，token 压缩保留语义。
  （此前 MiniMax-M3 窗口 1M、agnes-3.0-flash 512K，不设就是放任上下文涨到百万级。）
  ⚠️ 换模型时记得给新模型也设 `max_context_tokens`。
- **原生引用默认关闭**（`quote_reply_native=false`）：实测当前微信 4.x 的消息右键菜单是
  **自绘的、对 UIA 完全不可见**（右键 / 悬浮 / 先选中再右键三种方式均零新增控件、
  零新增顶层窗口），wxauto4 那套 `right_click + select_option("引用")` 在此版本上不可用。
  实现代码保留，将来微信版本变化可直接打开再试。
- **新增 `mention_as_text`（默认开）**：把 `at` 段降级成文字「@昵称 」，
  群里终于看得出这条回复在回谁；已自带 `@` 或 `@全体` 时不重复加。
- **面板补上黑名单文案（前端语言包）**：AstrBot 会把 schema 的 `description`/`hint` 转成
  i18n key（`ext_group.ltm.<path>.description`），真正显示的文字来自编译好的前端语言包
  （中/英/俄/日 4 种语言都内嵌在 `dashboard/dist/assets/index-*.js`）。只补 Python schema
  会导致面板显示**原始 key**。已用 `scripts/patch_astrbot_i18n_blacklist.py` 注入四语言条目。
- **桥接面板：平台 ID 白名单也改成勾选框**（原来只有主动回复的白/黑名单是勾选框）。
  抽出 `renderNameList`/`collectNameList` 两个通用函数，三处名单行为统一；
  不在已知群列表里的条目自动落入「自定义条目」框，不会丢。
- **新增 `sim/sim_test_suite.py`**：模拟器综合测试套件（10 项：功能如实答 / 模型名 /
  知识库 AK+终末地 / 称呼规则 / 语言跟随 英日 / 简洁度 / 上下文记忆），一键跑并输出汇总，
  实测 10/10 通过。
- **新增分析脚本** `scripts/analyze_log.py`、`scripts/analyze_mine.py`：统计各场景
  回复率、回复长度、分段情况（排障用，不参与打包）。

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
