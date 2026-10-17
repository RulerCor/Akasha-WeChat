# 漏收消息补偿工具 reply_missed.py 开发说明

> 位置：scripts/reply_missed.py | 创建：2026-10-13 | 归属：Akasha-Wechat_RC

## 1. 解决什么问题

WeFlow 是机器人的唯一消息入口（SSE 实时推送）。SSE 是纯推送、无补发机制：
WeFlow 宕机/重启/网络抖动窗口期里到达微信的消息，机器人永远收不到，AI 对其
"失忆"，对话断裂（实例：2026-10-13 11:28 洛辰私聊「qwq记我一笔啥呀」在停机
窗口漏收，bot 无法接梗）。

本工具把漏收消息**以发送者真实身份**补注入 AstrBot（延续原会话记忆与人设），
捕获 AI 生成的回复后经桥接同款 UIA 通道发回真实微信，并回读 WeFlow 历史库
做落库验证。

## 2. 四个模块

| 模块 | 职责 | 关键点 |
|---|---|---|
| config_identity | 读桥接配置、wxid→uid、联系人解析 | uid 算法与 state.py:_wxid_to_int **逐字节同源**，见红线一 |
| history_evidence | 从 WeFlow /api/v1/messages 找回漏收原文 | 只读；WCDB 不可用时先跑时间回拨脚本 |
| astrbot_injector | 独立 WS 注入 + 捕获回复 | 见红线二；事件格式对齐 ob_protocol.make_message_event 私聊分支 |
| uia_sender_bridge | UIA 发送（文字+图片）+ 落库验证 | 复用桥接 UiaSender；验证以历史库 isSend=1 为地面真值 |

## 3. 两条不能破的红线

### 红线一：uid 算法禁止单边改动

    uid = int.from_bytes(hashlib.md5(wxid.encode()).digest()[:8], "big") % 2**31

与 runtime/bridge/state.py:_wxid_to_int 必须永远逐字节一致（含 md5 截断位数
与取模）。改任何一边，AstrBot 会把同一个人当成全新会话：人设、记忆、管理员/
白名单身份全部丢失。桥接日志表现为"每个联系人出现两遍"。

### 红线二：注入身份与回复路由

- 注入连接 X-Self-ID: 99009901（INJECT_SELF_ID），与真桥接（state._self_id_int）、
  模拟器（sim/sim_wechat.py 的 99009900）三者互不相同；
- AstrBot aiocqhttp/api_impl.py 的 AKASHA 路由兜底补丁按 AKASHA_OB_EXCLUDE_SELF_IDS
  （默认含 99009900）排除非生产客户端；回复沿 event_ws 上下文路由——**只回到
  处理该事件的连接**（即本工具）。真桥接收不到该回复，故不会 UIA 重复发送。

## 4. 用法

    # 最常用：知道原文，直接补
    python scripts/reply_missed.py --wxid wxid_m8p54rfwfesr22 --text "qwq记我一笔啥呀"

    # 只记得关键词：从历史库自动定位（需 WeFlow 数据库可用）
    python scripts/reply_missed.py --wxid wxid_m8p54rfwfesr22 --find "记我一笔"

    # 先生成不发送，人工把关
    python scripts/reply_missed.py --wxid ... --text "..." --no-send

参数：--contact 覆盖 UIA 发送目标名；--timeout AI 回复总超时（默认 180s，
含 LLM 延迟）；--no-verify 跳过落库回读；详见 --help。

## 5. 依赖的前置状态

| 依赖 | 检查方式 | 不满足时的现象 |
|---|---|---|
| AstrBot 在线（ws://127.0.0.1:11229/ws） | 面板 /api/astrbot-status | 注入后无回复，超时退出 |
| WeFlow 运行中（5031） | curl /api/v1/health | contacts/历史取证失败 |
| WeFlow 数据库可用（WCDB 已连接） | GET messages 返回 200 | --find 不可用；验证退化为告警 |
| 微信 PC 打开且已登录 | 桌面可见微信窗口 | UIA 发送直接失败 |

> WeFlow 数据库受上游 -101 授权到期影响时，用项目根目录
> 临时启动WeFlow_时间回拨.bat（RunAsDate 冻结时钟 2026-09-30）拉起。

## 6. 已知边界

- 只支持私聊消息补偿（群聊 @ 关系/发言者映射复杂度高，暂不做）；
- 图片类漏收：历史库图片 URL 有时效，实践中直接 --text 描述内容更稳；
- AI 回复里的表情包走 base64 图片段，工具落临时文件经 send_image 发送后自动清理；
- 注入事件 time 字段用原消息时间：AstrBot 记忆排序正确，但 AI 对"现在几点"的感知仍以真实时钟为准。

## 7. 来源与演变

由 2026-10-13 两个一次性脚本合并而来（已删除）：scripts/_reply_luochen_inject.py（注入+捕获）、
scripts/_reply_luochen_send.py（UIA 发送）。

首战案例：洛辰「qwq记我一笔啥呀」补回复成功，双链路验证（UIA 返回 True + 历史库 isSend=1）均通过。