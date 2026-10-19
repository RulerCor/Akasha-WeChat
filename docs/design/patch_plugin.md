# akasha_rc_patches 补丁插件 — 设计文档

## 目标

AstrBot 升级会覆盖安装目录里的源码。`akasha_rc_patches` 插件把本项目需要的框架行为修正全部放到启动时执行：不改 AstrBot 源码、不残留补丁备份，升级后只要插件仍启用即可恢复。

## 当前补丁

| 补丁 | 作用 |
|---|---|
| active_reply_blacklist | 恢复 4.29 删除的群主动回复黑名单 |
| provider_getkeys | 单字符串 API Key 规范化为列表 |
| openai_read_timeout | 为 OpenAI 兼容通道增加读超时，防止流式响应永久挂起 |
| kb_wording_mgr | 知识库检索结果如实标注为资料 |
| kb_wording_agent | 非 agentic 注入头使用同样的知识库措辞 |
| kb_scope | API Key 获得知识库接口权限 |
| aiocqhttp_primary | 主动发送无事件上下文时的路由兜底 |
| cron_sender_name | 定时任务合成发送者名中性化 |
| group_alias_note | 群聊上下文中合并昵称/备注同名说明 |

人设规则保存在 `data_v4.db`，不属于本插件；`scripts/check_patches.py` 单独检查这些持久化规则。

## 数据

主动回复黑名单保存在：

```text
runtime/astrbot/data/plugin_data/akasha_rc_patches/active_reply_blacklist.json
```

结构为：

```json
{
  "entries": ["401396665"]
}
```

桥接面板保存“插嘴”开关时写入这份文件；AstrBot 配置中的旧 `active_reply.blacklist` 已不再是权威来源。

## 部署与验证

```powershell
python scripts/deploy_plugin.py akasha_rc_patches
python scripts/akasha_ctl.py restart
python scripts/check_patches.py
```

插件启动日志会逐项打印 ✅ / ⏭️ / ❌。微信中发送 `/akasha_patches` 也可查看状态。
