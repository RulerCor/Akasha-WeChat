# Alpha 原生接入说明（WeFlow 继任者）

> 建立日期：2026-10-18 ｜ 状态：**已实现并实测**（Alpha 0.2.0 / 微信 4.1.8.107）
> 相关：[`AGENT.md`](../AGENT.md) 红线、[`docs/WeFlow时间回拨启动套件.md`](WeFlow时间回拨启动套件.md)

## 0. 一句话

桥接新增**消息源选择**（`message_source`）：`weflow`（老链路，保留）或 `alpha`（原生 Alpha）。
选 `alpha` 时走 Alpha 自己的 HTTP API + SSE，**不再借用 WeFlow 的接口形态**。
发消息默认仍是 UIA；Alpha 的发送 API 已接上，但需要付费激活，未激活时自动退回 UIA。

## 1. 为什么换

- WeFlow 已停止维护，且带**授权时间炸弹**（wcdb_api.dll 过 2026-10-01 返回 -101），
  现在只能靠 RunAsDate 把进程内时钟冻结在 2026-09-30 才能读库。
- Alpha 是 WeFlow 的继任者：同样能读微信 4.x 本地库，**无时间炸弹**，
  自带 HTTP API + MCP，接口更全（会话/消息/搜索/联系人/群成员/朋友圈/导出/发送）。

## 2. 本机实测环境（2026-10-18）

| 项 | 值 |
|---|---|
| Alpha | `%LOCALAPPDATA%\Programs\Alpha\Alpha.exe`，版本 **0.2.0** |
| Alpha 安装包归档 | `installers_src/Alpha-0.2.0-x64-Setup.exe`（137,881,716 字节，sha256 `D89DBAB2…E4723529`） |
| 微信 | `C:\Program Files\Tencent\Weixin\Weixin.exe` → **4.1.8.107**（是 Weixin，不是老 WeChat.exe） |
| 会话库 | `%USERPROFILE%\Documents\xwechat_files\<wxid>\db_storage\session\session.db` |
| Alpha 数据 | `%APPDATA%\Alpha`（settings / vault / alpha-meta.db / alpha-jobs.sqlite3） |
| Alpha 运行时 | `%LOCALAPPDATA%\Alpha\Runtime`，二进制在 `…\Programs\Alpha\resources\bin\` |

**Alpha 账号**：账号 ID 与 wxid 都是敏感值，只写在 `runtime/bridge/config.json`（已 gitignore），
**不进仓库、不进日志**。

### 端口冲突（重要）

Alpha 与 WeFlow 的 HTTP API **默认端口都是 5031**，两个同时开必然冲突
（Alpha 端口被占时启动会直接失败并提示，不会自己换端口）。

本机最终分配：

| 服务 | 端口 |
|---|---|
| WeFlow | 5031（老链路，保留作回滚） |
| **Alpha** | **5030** |

换端口：Alpha →「设置 → 接口与集成 → 本机 HTTP API」填端口 →「保存并启动」。
需要实时推送时必须**同时打开同页的「主动推送」**，否则 `/api/v1/push/messages` 返回 409 `HTTP_API_PUSH_DISABLED`。

## 3. 配置项（`runtime/bridge/config.json`）

```jsonc
{
  "message_source": "alpha",          // "weflow" | "alpha"；默认 weflow（向后兼容）
  "alpha_base_url": "http://127.0.0.1:5030",
  "alpha_access_token": "<Alpha 访问令牌>",
  "alpha_account_id": "",             // 留空 = 启动时自动从 /api/v1/accounts 取唯一就绪账号
  "send_method": "uia",               // "uia"（默认）| "alpha_api"
  "alpha_send_wait_seconds": 30
}
```

WeFlow 相关字段（`weflow_base_url` / `access_token`）**原样保留**，选 `alpha` 时不用它们。

> ⚠️ 令牌写在 `config.json`，该文件已在 `.gitignore`；公开前请勿 `git add -f`。

## 4. 两条链路差异（桥接已抹平）

| 关注点 | WeFlow | Alpha |
|---|---|---|
| SSE 订阅 | `GET /api/v1/push/messages?access_token=…` | `GET /api/v1/push/messages?accountId=<账号ID>`，**accountId 必填** |
| 鉴权 | 全部走 query `access_token` | `Authorization: Bearer <token>`（也支持 query，但会记日志） |
| 群消息发言人 | `sourceName` = 昵称 | `sourceName` = **发言人 wxid**（群名在 `groupName`） |
| 时间戳 | 秒 | 秒（一致） |
| 群成员 | `GET /api/v1/group-members?talker=<room>` | `GET /api/v1/group-members?chatroomId=<room>`（**参数名不同**） |
| 取图 | `/api/v1/messages?talker=…&media=true` → `mediaUrl` | 同路径但返回 `media.resources[]` / `mediaUrl`，URL 需带 Bearer 头 |
| 发送文字 | ❌ 无发送接口 | `POST /api/v1/messages/send-text`（需付费激活） |
| 历史上限 | — | 每轮最多 128 个「最近 60s 有活动」的会话；只推连接后到达的消息，不回放 |

### Alpha SSE 消息字段（实测）

```json
{"event":"message.new","eventId":"message.new:<sessionId>:<rawid>",
 "accountId":"…","sessionId":"12345@chatroom","sessionType":"group",
 "rawid":"1303632778555730573","avatarUrl":"https://…",
 "sourceName":"<发言人wxid>","groupName":"某群",
 "content":"纯文本 或 微信原生 XML","timestamp":1792305254}
```

- `event` ∈ `stream.ready` / `message.new` / `message.revoke` / `stream.error`
- 收到 `stream.error` 后**连接会被关闭**，需重连（桥接外层循环已处理）
- 去重键：`event + rawid`

### 内容形态（实测，与 WeFlow 不同）

- **图片/表情/视频在 SSE 里是微信原生 XML**（`<img>` / `<emoji …md5=… cdnurl=… >` / `<videomsg>`），
  不像 WeFlow 那样已经归一化成 `[图片]` / `[表情]` 占位符。
  桥接的 `message_source` 会把它们分类成 `[图片]` / `[表情]` / `[视频]`，并把原始 XML 留在 `_alphaRawContent`。
- 链接/文件/合并转发仍是 `<appmsg>` XML，交给 `wx_msg_parser` 归一化（与 WeFlow 同一条路）。
- 取真实字节：`/api/v1/messages?talker=X&media=true` 的 `media.resources[0].url`
  或 `mediaUrl`，值是 `/api/v1/media/<opaque>`，**下载要带 Bearer 头**。

## 5. 发送：默认 UIA，Alpha API 需要激活

- `send_method: "uia"`（**默认**）：走 Windows UIA 操作微信窗口，不花钱、已验证。
- `send_method: "alpha_api"`：走 `POST /api/v1/messages/send-text`。
  需要 Alpha 里**激活「发送文字消息」**（据官方渠道约 ¥100/月）并在
  「高级功能 → 发送文字消息」连接一次微信。未激活时返回 409 `SEND_CONNECTION_REQUIRED`，
  桥接会**打日志并按失败处理**（不会静默假成功）。

实测（2026-10-18，本机未激活）：

```
POST /api/v1/messages/send-text {"username":"filehelper","text":"…"}
→ 409 {"error":{"code":"SEND_CONNECTION_REQUIRED","message":"…"}}
```

所以本项目的默认保持 `uia`。想试 Alpha 原生发送就把 `send_method` 改成 `alpha_api`，
并在文档/`CHANGELOG.md` 里记一笔结果。

**后续可选路线**：逆向 Alpha 的 `alpha-message-send.exe` / `ALPHA_GATEWAY_BEARER`
协议，绕过付费激活（用户提出的 REA 方向，尚未做）。

## 6. 切换与回滚

### 切到 Alpha
1. 打开 Alpha，确认账号已连接（设置页显示 ready）。
2. 「设置 → 接口与集成 → 本机 HTTP API」：填端口（本机用 **5030**）、填/生成访问令牌、「保存并启动」。
3. 同一页打开「主动推送」并应用。
4. 面板 `http://127.0.0.1:8766` →「基础设置 → 连接」：消息源选 `alpha`，填 Alpha 地址与令牌。
5. 保存后重启桥接（面板「停止」→「启动」，或重启 `一键启动.bat`）。

### 回滚到 WeFlow
把 `message_source` 改回 `weflow` 即可 —— WeFlow 的代码路径**一行没删**，
包括 RunAsDate 时间回拨启动方式（见 `docs/WeFlow时间回拨启动套件.md`）。

## 7. 已知限制 / 坑

- **Alpha 桌面必须开着**，且应用锁定时 API 会暂停（解锁自动恢复）。
- 端口冲突见 §2：5031 只能有一个。
- Alpha **只推连接之后到达的消息**，不回放历史，不支持 `Last-Event-ID`；
  断线期间的消息要用 `/api/v1/messages` 补拉（桥接目前不做自动补拉，靠 WeFlow 一旦停用后
  `scripts/reply_missed.py` 那种工具，注意该工具目前只认 WeFlow 接口）。
- 每轮最多 128 个「最近 60s 有活动」的会话；会话总数不受限。
- 群成员接口参数名是 `chatroomId`，**不是** `talker`（容易踩）。
- Alpha 群成员返回的字段是 `wxid` / `groupNickname` / `nickname` / `remark` / `displayName` / `alias`
  （和 WeFlow 的 `members[]` 形状兼容，`set_group_roster` 直接能用）。
- 微信大版本兼容性：Alpha 官方没有公开的「支持版本表」。
  本机 4.1.8.107 实测可用；社区反馈部分 4.1.13/4.1.15 构建在 macOS 上出过问题。
  **换微信版本前先在 Alpha 里确认账号 state=ready、能读到消息**，再切桥接。
- Alpha 闭源，出问题只能等上游；这就是**保留 WeFlow 回滚路径**的原因。

## 8. 代码落点

| 文件 | 改动 |
|---|---|
| `config.py` | 新增 `MESSAGE_SOURCE` / `ALPHA_BASE_URL` / `ALPHA_ACCESS_TOKEN` / `ALPHA_ACCOUNT_ID` / `ALPHA_SEND_WAIT_SECONDS`；`send_method` 归一化（`weflow_api` → `uia`） |
| `message_source.py` | **新增**：消息源抽象。`WeFlowSource` / `AlphaSource`，统一 SSE URL、鉴权头、contacts / group-members / messages 参数、SSE 载荷归一化 |
| `bridge_core.py` | `refresh_contact_names` / `_prefetch_group_rosters` / `listen_sse` / 取图 / 启动自检 改为走 `message_source`；支持 `senderWxid` 直传 |
| `senders.py` | 新增 `AlphaApiSender`；工厂不再选 `weflow_api`（`WeFlowApiSender` 类保留但标注废弃） |
| `web_panel.py` | 「连接」组加消息源选择 + Alpha 3 项；「发送方式」选项改为 `uia` / `alpha_api`；`/api/detect-bot` 支持 Alpha |
| `scripts/watch_services.py` | 按 `message_source` 决定探活端口，选 alpha 时不要求 RunAsDate |
| `config.example.json` | 同步新增字段 |

## 9. 验证记录（2026-10-18）

- `GET /api/v1/accounts`（Bearer）→ `count:1`，`ready:true`、`selected:true` ✅
- `GET /api/v1/sessions?limit=5` → 28 个会话，`sessions[]` 与 `items[]` 双格式 ✅
- `GET /api/v1/messages?talker=filehelper&limit=2` → 正常返回 ✅
- `GET /api/v1/contacts?usernames=<wxid>` → 精确命中 ✅
- `GET /api/v1/group-members?chatroomId=<room>` → 17 名成员，含 `wxid` ✅
- SSE `GET /api/v1/push/messages?accountId=<id>` → 先收 `stream.ready`，
  随后持续收到真实 `message.new`（含群文本与 XML 表情）✅
- `GET /api/v1/push/status` → `enabled:true`、`maxSubscribers:8` ✅
- `POST /api/v1/messages/send-text` → 409 `SEND_CONNECTION_REQUIRED`（未激活，符合预期）✅
- `POST /mcp` (Bearer) `tools/call wechat.contacts.get_group_members` → 正常返回 ✅
