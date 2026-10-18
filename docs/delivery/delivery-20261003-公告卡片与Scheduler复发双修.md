# 交付说明：公告卡片压断 ws + 「Scheduler博士」复发双修（2026-10-03）

## 用户报告

1. 「官方新公告」发送后什么都没发送（只有文字，无卡片）；
2. 「呜，Scheduler博士怎么又丢一大段字过来喵」——Scheduler 称呼复发。

## 问题①：公告卡片丢失

### 证据链（bridge.log + astrbot.log）

| 时间 | 事件 |
|---|---|
| 11:16:43 | 文字「官方新公告」发到群 ✅ |
| 11:16:43 | OB11 连接断开（`[OB11] 连接断开，5 秒后重连`） |
| 11:16:48 | 重连成功 |
| 11:19:43 | AstrBot `发送消息失败: WebSocket API call timeout` |

卡片：`render_cache/render_fe0b9399.jpg` = 900×9623px / 1.5MB JPEG → base64 约 2MB/帧。

根因：桥接 `websockets.connect()` 未设 `max_size`，websockets 15.x 默认收帧上限
**1MB** → 2MB 帧触发超限断连；AstrBot 侧 `api_timeout_sec=180` 等满超时。

### 修复

- `wechat-weflow-bridge-ob11/ob_client.py`：`max_size=16MB`（用户拍板保留卡片图形式）；
- `astrbot_plugin_arknights/main.py`：公告卡片渲染后 >8MB 降级纯文本（保险丝，
  防渲染异常超大图拖垮连接）。

## 问题②：「Scheduler博士」复发

### 根因（换路径）

2026-10-01（`3a655d2`）只修了 companion 私聊身份锚点一条路。本次走
**wanna_be_human 主动聊天**：

```
_generate_proactive_reply 构造 CronMessageEvent 未传 sender_name
→ 核心默认 "Scheduler"（core/cron/events.py:24）
→ group_chat_context 前缀 [Scheduler/10:38:33]:
→ 模型模仿称呼（10:38:40 实发「Scheduler博士怎么又丢一大段字过来喵」）
```

日志核查：`Prepare to send - Scheduler/xxx` 309 次（10-01～10-03）；
活跃历史残留 conversations 4 条 + companions.json 18 处
（含 `sender_label` 5 处——`event_dispatch.py:1699` 路径上次未覆盖）。

### 修复（三层收敛 + 数据清理）

1. **核心治本**：`scripts/patch_cron_sender_name.py` 把默认名换成中性
   「系统日程」（带标记可还原 `off`）；注册进 `akasha_rc_patches` PATCHES
   （8→9 项，pip 升级自动重打；发布源拷贝 `scripts/akasha_rc_patches_plugin/`
   已同步）；
2. **插件显式名**：wanna_be_human 显式传「系统日程」；private_companion
   `proactive_message.py` 的 `"PrivateCompanion"` 同款人名词形预防性更换；
3. **companion 源头隔离**：`event_dispatch.py _sender_display_name` 加
   `_sanitize_synthetic_sender_name`，在取名源头拦掉 "Scheduler"，
   4 个调用点（身份锚点/注入事件/群观察等）自动受益；
4. **数据清理**：`scripts/scrub_scheduler_residue.py` 替换 conversations 4 处 +
   companions.json 18 处（「Scheduler博士」→「博士」）。复核残留 0。
   `platform_message_history` 4 行发送留档故意不动（防引用错位）。

## 验证（12:44 重启后）

- `akasha_ctl.py status`：AstrBot :11229/:6185 pid=10752 ✅、桥接 :8766 pid=8316 ✅；
- 补丁日志 12:44:56：`Cron 合成发送者名中性化 → 状态: 已打`（5/9 项生效）；
- 桥接 OB11 12:46:11 重连成功，群名册 324 条映射正常；
- 语法校验：全部改动文件 `py_compile` 通过；核心 events.py 补丁标记在位。

## 备份清单

- `runtime/astrbot/data/data_v4.db.bak_scheduler2_20261003`
- `runtime/astrbot/data/plugin_data/astrbot_plugin_private_companion/companions.json.bak_scheduler2_20261003`
- `.../astrbot_plugin_wanna_be_human/main.py.bak_scheduler2_20261003`
- `.../astrbot_plugin_private_companion/event_dispatch.py.bak_scheduler2_20261003`
- `.../astrbot_plugin_private_companion/proactive_message.py.bak_scheduler2_20261003`
- `.../astrbot_plugin_arknights/main.py.bak_card_20261003`

## 提交

`67fab58`（5 files, +304）——CHANGELOG、ob_client、两个新脚本、补丁插件源拷贝。
运行时插件副本与核心 site-packages 补丁不入库（.gitignore `runtime/`），
由 `akasha_rc_patches` 插件每次启动自动重打。

## 观察点

- 下次主动聊天/cron 消息上下文前缀应为 `[系统日程/…]`，不得再出现「Scheduler博士」；
- 下一条超长公告卡片应完整到群（文字+卡片图）。
