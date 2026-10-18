# 交付说明：无畏契约知识库 + 黑梦人设卡（2026-10-06）

## 需求

1. 增加《无畏契约》(VALORANT) 知识库；
2. 增加黑梦（Fade）这个角色的人设卡。

用户决策：
- 人设卡进**人设池备用**（不切主群，主群仍是 mon3tr）；
- KB 挂载由用户自己在面板选择（**本次不绑任何会话**）。

## 交付物

### 知识库 `valorant`（kb_id `c959a2ff-1bb2-48f8-9acb-572e72885f11`）

- 6 篇文档（`runtime/astrbot/kb_docs/valorant_*.md`）：游戏概览 / 29 特务总览 /
  黑梦专档 / 地图与武器 / 社区梗 / 索引 README；
- 资料来源：Riot 官方 zh-CN 本地化（valorant-api.com 镜像，2026-10-06 采集）
  + 社区通行用法整理；技能/地图/武器均为国服官方译名
  （黑梦=先锋；黯兽 C / 幽爪 Q / 诡眼 E / 夜临 X）；
- 配置与现有库一致：`siliconflow/BAAI/bge-m3`，chunk 512/50，top 50/50/5；
- 37 块全部向量化，**faiss 对账 37/37**（见下）。

### 人设卡 `fade`（黑梦）

- `scripts/add_persona_fade.py`：幂等插入 personas 表，prompt 3170 字，
  已备份 `data/backup/persona_fade_20261006_165338.txt`；
- 段落结构与明日方舟四人格同源：COMMON 八段 +
  **原生自带**「资料相关性判断」「发言归属与身份守则」两段——
  `check_patches.py` 12 项全绿，无需重打补丁；
- 走 persona_mgr 内存路径创建，**免重启即生效**（面板/`/persona` 可见）。

### 导入脚本 `scripts/import_valorant_kb.py`

建库 → 逐篇上传 → **轮询任务完成再传下一篇** → faiss/docdb 对账。

## 发现并修复的存量 bug：并发导入导致向量索引缺块

**现象**：首次导入后检索「命中恒为同一块、分数恒 0.900」，负样本查询也高分。

**根因**（`data/knowledge_base/*` 实测对账）：

| 知识库 | kb.chunk_count | faiss 向量数 | docdb 行数 |
|---|---|---|---|
| valorant（并发导入后） | 37 | **9** | 37 |
| persona3（9 月导入，存量） | 107 | **32** | 107 |
| arknights / naruto / generic / endfield / 风格库 | — | ✅ 一致 | ✅ 一致 |

上传文档是后台任务，每个任务各自「读 index.faiss → add 向量 → 写回」，
**并发时后者整体覆盖前者**——文档库 37 条都在，向量索引只剩最后一批 9 条。
密度检索查的正是 faiss，被覆盖掉的块永远检索不到。persona3 库 9 月就这样
丢了 75/107 块（（长尾问题：库小、召回本来就少，一直没暴露）。

**修复**：`import_valorant_kb.py` 改为逐篇串行（等 `tasks/{id}` 到
completed/failed 再传下一篇）+ 完成后 faiss 对账。重跑后 37/37 ✅，
检索恢复正常（「黑梦的大招」1.000 命中夜临条目）。

**未动的东西**：
- persona3 库的 32/107 缺块是存量问题，修复路径就是重跑
  `import_persona3_kb.py`（该脚本还未改串行，直接重跑会复现缺块——
  如需修复建议先把本脚本的串行+对账逻辑移植过去再跑）；
- 6 个会话的 `kb_config` 一概未动；全局 `kb_names=["arknights","endfield"]`
  未动。valorant 库挂到哪个会话由博士在面板自行选择
  （`/api/v1` 或 面板「知识库」页 → 会话配置）。

## 验证

1. `scripts/add_persona_fade.py --verify`：fade 存在、8 个必需段落齐全 ✅
2. `scripts/check_patches.py`：12/12 全绿 ✅（fade 原生携带两段全局补丁）
3. KB 检索冒烟（`POST /knowledge-bases/{id}/retrieve`）：
   - 「黑梦的大招叫什么？什么效果」→ 1.000 命中「夜临（Nightfall）」✅
   - 「冥驹多少钱」→ 1.000 命中狙击枪价格表 ✅
   - 「下包是什么意思」→ 0.900 命中社区用语条目 ✅
   - 「光辉的r怎么放」（LoL 噪声）→ 低区分度分数，靠人设
     「资料相关性判断」段兜住，不会把瓦资料硬安到别游戏话题上 ✅
4. faiss 对账：37/37 ✅

## 后续观察点

- 主群仍是 mon3tr，无任何行为变化；
- 若切某会话到 fade：面板选 persona=fade + 把 valorant 库挂到该会话即可；
- persona3 库缺块若要修：移植串行逻辑后重跑 import_persona3_kb.py。
