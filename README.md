# Mon3trBot_Remake

**English** | [中文](#中文)

Mon3trBot_Remake connects a personal WeChat account to AstrBot through a Windows bridge. WeFlow or Alpha supplies incoming messages, the bridge translates them to OneBot v11, and AstrBot handles models, personas, knowledge, tools, and scheduled tasks. Outgoing messages are sent through WeChat's desktop UI.

This project is a maintained fork of [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat). The bridge directory keeps the upstream name so changes remain easy to compare and merge.

## Features

- Stable OneBot v11 sessions across bridge restarts
- WeFlow and Alpha message sources
- Windows UIA sending with an optional Alpha API sender
- Web control panel for startup, configuration, logs, members, permissions, and AstrBot restarts
- Group reply and proactive-chat controls, plus a private-chat allowlist
- AstrBot runtime patches packaged as a plugin, so framework upgrades do not require source edits
- Character personas and ordinary knowledge-base documents included in release builds

## Requirements

- Windows 10/11
- WeChat desktop and WeFlow (or a configured Alpha account)
- Python 3.13 for development
- AstrBot and a configured language-model provider

The release ZIP is self-contained: Python, AstrBot, the bridge, and installers are included. Development users can run the local runtime instead.

## Quick Start

1. Extract the release ZIP to a short path.
2. Double-click `启动 Mon3trBot.bat`.
3. Open the bridge panel at <http://127.0.0.1:8766>.
4. Configure the WeChat account, message source, and AstrBot connection.
5. Open AstrBot's WebUI at <http://127.0.0.1:6185> and configure the model, personas, and knowledge base.
6. Add friends or groups through **Members & Permissions**, save, and restart AstrBot when prompted.

To stop all services, double-click `停止 Mon3trBot.bat`.

## Architecture

```text
WeChat <-> WeFlow / Alpha --SSE--> bridge --WebSocket--> AstrBot
                                      |
                                      +--> Web panel :8766
                                      +--> UIA sender / Alpha API
```

- `wechat-weflow-bridge-ob11/`: bridge source, protocol conversion, panel, and senders
- `scripts/akasha_rc_patches_plugin/`: runtime patches owned by this project
- `sim/`: offline conversation simulator
- `docs/`: development, deployment, and troubleshooting notes
- `runtime/`: local runtime data and virtual environments (not committed)
- `release/`: build outputs and release history (not committed)

## Development

```powershell
python scripts/check_patches.py
python scripts/test_aiocqhttp_routing.py
python scripts/test_alias_note.py
python scripts/test_ob_segments.py
```

After changing a plugin, deploy it with:

```powershell
python scripts/deploy_plugin.py akasha_rc_patches
```

See [AGENT.md](AGENT.md) for maintenance rules and [CHANGELOG.md](CHANGELOG.md) for release history.

## Privacy

Never commit `config.json`, API keys, access tokens, chat history, contact lists, group names, or runtime databases. Release builds are sanitized and audited before packaging.

## License and Credits

MIT, following the upstream project. Built on [Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat), [AstrBot](https://github.com/AstrBotDevs/AstrBot), and [WeFlow](https://weflow.top).

---

## 中文

Mon3trBot_Remake 是一个把微信个人号接入 AstrBot 的 Windows 桥接项目。WeFlow 或 Alpha 负责接收消息，桥接将其转换为 OneBot v11，AstrBot 负责模型、人格、知识库、工具和定时任务，最终由微信桌面端完成发送。

本项目是 [alingalingling/Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat) 的持续维护分支。桥接目录沿用上游名称，便于对照和合并更新。

## 功能

- 桥接重启后会话 ID 保持稳定
- 支持 WeFlow 与 Alpha 两种消息源
- 默认使用 Windows UIA 发送，也可配置 Alpha API 发送
- Web 面板可启动服务、修改配置、查看日志、管理成员权限并重启 AstrBot
- 群聊回复与主动插话开关，私聊白名单独立管理
- AstrBot 修复以插件形式在运行时加载，升级框架无需改源码
- 发行版包含角色人格与普通知识库文档

## 环境要求

- Windows 10/11
- 微信桌面端，以及 WeFlow（或已配置的 Alpha 账号）
- 开发环境使用 Python 3.13
- AstrBot，以及已配置的大模型服务

发行版压缩包已包含 Python、AstrBot、桥接和安装包，解压即可使用。

## 快速开始

1. 将发行版解压到较短路径。
2. 双击 `启动 Mon3trBot.bat`。
3. 打开桥接面板 <http://127.0.0.1:8766>。
4. 配置微信账号、消息源和 AstrBot 连接。
5. 打开 AstrBot WebUI <http://127.0.0.1:6185>，配置模型、人格和知识库。
6. 在「成员与权限」中勾选好友或群，保存后按提示重启 AstrBot。

停止全部服务：双击 `停止 Mon3trBot.bat`。

## 架构

```text
微信 <-> WeFlow / Alpha --SSE--> 桥接 --WebSocket--> AstrBot
                                      |
                                      +--> Web 面板 :8766
                                      +--> UIA 发送 / Alpha API
```

- `wechat-weflow-bridge-ob11/`：桥接源码、协议转换、面板与发送器
- `scripts/akasha_rc_patches_plugin/`：本项目维护的 AstrBot 运行时补丁
- `sim/`：离线对话模拟器
- `docs/`：开发、部署与排障文档
- `runtime/`：本地运行数据与虚拟环境（不入库）
- `release/`：构建产物与历史版本（不入库）

## 开发

```powershell
python scripts/check_patches.py
python scripts/test_aiocqhttp_routing.py
python scripts/test_alias_note.py
python scripts/test_ob_segments.py
```

修改插件后部署：

```powershell
python scripts/deploy_plugin.py akasha_rc_patches
```

维护约定见 [AGENT.md](AGENT.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 隐私

不要提交 `config.json`、API Key、访问令牌、聊天记录、联系人名单、群名或运行数据库。发行版会在打包前完成脱敏与审计。

## 许可证与致谢

MIT，沿用上游项目。感谢 [Akasha-WeChat](https://github.com/alingalingling/Akasha-WeChat)、[AstrBot](https://github.com/AstrBotDevs/AstrBot) 与 [WeFlow](https://weflow.top)。
