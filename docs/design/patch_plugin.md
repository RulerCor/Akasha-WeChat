# akasha_rc_patches 补丁插件 — 设计文档

## 为什么插件化
AstrBot 每次 `pip install -U astrbot` 都会覆盖 site-packages，源码补丁全部丢失。
插件（`data/plugins/akasha_rc_patches/`）不随升级消失，加载时做运行时修改。

## 两类补丁
| 类型 | 方式 | 补丁 |
|---|---|---|
| 运行时 monkey-patch | 修改内存中的类/函数，升级天然免疫 | get_keys 归一化、OpenAI read timeout |
| 源码文件补丁 | import 执行 scripts/ 下幂等脚本 | kb 措辞×3、kb_scope、aiocqhttp 路由、i18n 文案 |

## 已修事故（为什么有这些补丁）
1. **get_keys str 崩溃**（2026-09-19）：单 key 源写成 str，`.copy()` 崩 → 所有模型失败。
2. **流式响应挂起**（2026-09-20）：openrouter 免费渠道 chunked body 不终止，
   httpx 无 read timeout → agent 任务永久挂起、无异常无回复。
   修复 = httpx.Timeout(read=180)。
3. **检索结果绑架话题**（2026-09-19 21:16）：无关档案被召回，bot 顺着演——
   人设层补丁「资料相关性判断」（personas 表，不在本插件）。
4. **KB 措辞**（2026-09-16）：上游把知识库注入说成"你想起来的记忆"→
   bot 编造亲身经历。改为【知识库】资料+三条使用要求。
5. **kb scope 403**：API key 无法调知识库接口 → 导入管道瘫痪。

## 关键实现细节
- `_run_patch_script()`：importlib 同进程执行补丁脚本（subprocess 在 vendor
  python 下读输出会挂）；捕获 stdout；注入 argv；StringIO 需补 `buffer` 属性
  （脚本头部有 TextIOWrapper 重定向）。
- `openai_source.create_proxy_client` 是 `from ... import` 绑定，替换
  network_utils 后必须**同步替换 openai_source 模块命名空间里的引用**。
- 幂等：源码层补丁脚本自带"已是新版跳过"；运行时补丁用
  `_akasha_*_patched` 标记防重复。

## 状态命令
微信发送 `/akasha_patches` → 返回各项 ✅/⏭️ 状态。

## 升级 AstrBot 后的恢复流程
1. 重装本插件（从 `scripts/akasha_rc_patches_plugin/` 复制到
   `data/plugins/akasha_rc_patches/`）
2. 重启 → 启动日志逐项确认
3. `python scripts/check_patches.py` 应全绿（人设 5 段 + 插件 8 项）
