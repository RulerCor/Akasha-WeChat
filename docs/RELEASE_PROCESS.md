# 版本归档流程（v1.5.3 起强制执行）

每次发版（或每完成一批可独立叙述的改动）必须走完以下 7 步，缺一不可。

## 1. 版本号
- 语义化：`主.次.修订`。修复→修订位，新功能→次位，破坏性→主位。
- 同步改两处：`wechat-weflow-bridge-ob11/VERSION` 与 `runtime/bridge/VERSION`。

## 2. CHANGELOG.md
- 顶部新增 `## [x.y.z]（日期）` 条目：新增/修复/变更/验证。
- 每条附带**事故现场**（日志证据）与**验证方式**，不写空话。

## 3. git tag
```bash
git tag -a vX.Y.Z -m "一句话说明" && git push origin vX.Y.Z
```
- **每个 release 版本号都必须有对应 tag**（历史上 v1.5.0/1.5.1 无 tag，已补记为教训）。

## 4. 发行版（对外交付时）
- `python scripts/build_dist.py` → 隐私审计全过 → zip 进 `release/dist/`。
- `python scripts/audit_dist.py` 全项 PASS。
- GitHub Release + notes（照抄 `release/issues/release_notes_v152.md` 结构）。

## 5. 补丁快照
- AstrBot 补丁状态必须 `python scripts/check_patches.py` 全绿。
- 补丁清单有增删时，同步 `scripts/akasha_rc_patches_plugin/`（插件源码）。

## 6. 开发文档
- 新增子系统/模块 → `docs/` 下补一页（设计要点 + 关键决策 + 已知坑）。
- 现有文档：`docs/architecture.*`（架构图）、本文件。

## 7. 证据归档
- 验证输出/截图存 `release/verify/`（含 EVIDENCE.txt 清单）。
- `release/verify/` 不进 git（.gitignore），仅本地与发行包。

## 历史补记（2026-09-20）
- v1.0.0 ~ v1.4.0：无 tag、无发行 zip（当时无归档习惯）——CHANGELOG 可追溯，不再补 tag。
- v1.5.0 / v1.5.1：zip 在 `release/dist/`，无 tag、无 GitHub Release。
- v1.5.2：首个全流程归档版本（tag + GitHub Release + 审计）。
