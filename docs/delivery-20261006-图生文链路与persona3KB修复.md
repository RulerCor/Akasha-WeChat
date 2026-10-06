# 交付说明：图生文链路排障 + persona3 KB 向量补齐（2026-10-06 晚）

第 5 轮维护，两件独立的事：①「bot 看不见图」链路排障（结论：外部转发网关
剥图，用户侧修复，本项目零改动）；② persona3 知识库向量缺口精确修复
（`53bfd1c`，新增一个脚本，不重传文档）。

## 一、图生文链路排障

### 现象与定性

群内两例「看不见图」，性质不同：

| 案例 | 定性 | 依据 |
|---|---|---|
| bot 回复「能看的喵，上面还印着一行『我目前没有看到你上传的图片』」 | **模型幻觉** | 被引用的「图注」在 200 条会话上下文中不存在（dump conversations 逐条核对）；与其自身历史「图片过来就是一片空白」的诚实模式相反，是反向编造 |
| bot 回复「是这图我这边还是一片空白喵」 | **真实故障的诚实报告** | 链路当时确实收不到图，见下 |

### 根因：外部转发网关剥离 image_url

图片链路：主模型（dsv4-flash，`modalities=['text','tool_use']`，无视觉）收到
带图消息 → 核心触发图生文（caption）→ caption 供应商收到的请求里图是
OpenAI 风格 content parts `[{type:text},{type:image_url,…}]`。

**用户自有转发网关（内网中转，托管多家通道）在转发时把 `image_url` 部分
整段剥掉、只留文本**——所以任何挂在该网关的模型都「没收到图」，与模型、
通道无关。探针矩阵（1×1 红像素 + 远程 URL 双测，`max_tokens≥300`）：

| 通道/模型 | 修复前 | 用户修网关后 |
|---|---|---|
| 转发网关上 5 个 dsv4.1f 通道 | ❌ 全部「没收到图」 | ✅ |
| 转发网关 glm-5.3f | ❌ | ✅「深红色」 |
| 其中 1 个通道另报 HTTP 502（网关侧权益问题） | — | 未复测 |
| 本地网关（对照，同模型名） | ✅ 一直正常 | ✅ |

**定性为通道共性，反馈用户修复；本项目配置零改动**（caption 供应商
`antijaypcdsh/trae/deepseek-v4.1-flash` 保持原样）。修复后复验两模型均
真实读图。AstrBot 无需重启：图生文是每请求现跑的。

### 排障过程中的两个独立发现（未改，记录备查）

1. **16:31 群图丢失**：bridge 推图（16:31:58）落在 AstrBot 重启空窗
   （16:31:33→16:32:14，插件加载 ~90s），日志「推送 1 张图片」后无
   「✅ 已推送」。一次性事件，非系统性 bug。
2. **模型幻觉倾向**：主模型在「图注说没图」时可能反向编造图注内容。
   未动人设/配置（需用户拍板）；候选缓解：人设加「没图就直说，不要想象」。

### probe 方法备忘（复用价值）

- OpenAI 风格 POST `{base}/chat/completions`，content parts 混合
  文本 + `data:image/png;base64,…`（1×1 红像素常量）+ 远程图 URL 各测一次，
  可区分「剥 image_url」vs「剥整个多 part」vs「拒远程图」；
- `max_tokens` 给小了会只有 reasoning 没正文，≥300 并同时读
  `reasoning_content` 与 `content`；
- 部分网关 429 限速，探针要带重试/间隔。

## 二、persona3 KB index.faiss 向量补齐

### 盘上实测（修复前）

第 4 轮已确认 persona3 存量缺块（当时口径 75/107）。本次精确对账：

| 项 | 数 | 说明 |
|---|---|---|
| doc.db（切块文本） | 107 块 | **完好无损**，FTS 稀疏检索一直正常 |
| index.faiss | 32 条 | 其中 **17 条真实**（全属 tartarus 篇）+ **15 条幽灵** |
| 幽灵 id | 75–89 连续 | 指向早已不存在的旧行，2026-09-20 并发覆盖事故残留 |
| **实际缺口** | **90 条** | 角色/面具/世界设定/年表/术语 5 篇一条向量都没有 |

> 之前口头说的「缺 75」未剔除幽灵，实际比设想更糟：缺口 = 107 − 17。
> 稀疏检索（走 doc.db 文本）一直在兜底，所以表现为「能搜到但语义召回差」，
> 长尾未暴露。

### 修复方式：补向量，不重传文档

文本本来就齐，重传有二次并发覆盖风险。新脚本
`scripts/fix_persona3_faiss.py`（默认 dry-run，`--apply` 写盘）：

1. doc.db 全量 107 块 ↔ faiss 现存 id 对账 → 算出缺 90 / 幽灵 15；
2. 缺的 90 块走与 AstrBot 入库同源的 embedding 路径重嵌
   （siliconflow BAAI/bge-m3，1024 维，`get_embeddings_batch` batch=16）；
3. `IndexIDMap.remove_ids(幽灵)` + `add_with_ids(缺)` → 写盘 → 复读对账。

不动 doc.db / FTS / 文本。修复前备份留在库目录：
`doc.db.bak_20261006`、`index.faiss.bak_20261006`。

### 踩过的坑（脚本已绕开）

- `get_embeddings_batch` 的 `progress_callback` 是被 `await` 调用的，
  **必须传 async 函数**，传同步函数报 `object NoneType can't be used in
  'await' expression`；
- REST 检索端点：`POST /knowledge-bases/{kb_id}/retrieve`，body **必须带
  `kb_names: [<库名>]`**（缺了报「缺少参数 kb_names」）；
  `POST /knowledge-bases/retrieve`（无 id）是 405 陷阱；
- 独立 python 进程 import astrbot.core 会触发循环导入（kb_mgr↔star.context），
  探针直接走 REST，别 import 核心。

### 验证

1. 对账（写盘后 + 重启后各一次）：faiss=107 / docstore=107 / 幽灵=0 / 缺=0 ✅
2. 重启加载新索引（重启前预告过空窗）后 REST 检索三域命中：
   - 「结城理的人格面具是什么」→ 5 条（characters + personas + terms）✅
   - 「无气力症是什么病」→ 5 条（terms + timeline + world_settings）✅
   - 「塔尔塔罗斯的楼层结构」→ 5 条（tartarus，修复前对照组）✅

## 未动的东西

- 主群人设、caption/主模型 provider 配置、6 会话 kb_config、全局
  `kb_names=["arknights","endfield"]`——一概未动；
- 16:38 幻觉未改人设（候选缓解待用户拍板）；
- 16:31 空窗丢图未做机制性处理（重启预告流程已有，频率低）。

## 复现/回滚

- 复现修复：`python scripts/fix_persona3_faiss.py`（dry-run 看对账数字）→
  `--apply` 写盘 → 重启 AstrBot 生效；
- 回滚：把 `index.faiss.bak_20261006` / `doc.db.bak_20261006` 改回原名
  （doc.db 本次实际未被改动，仅备份）；
- `import_persona3_kb.py` 本体仍是并发版（未按第 4 轮建议改串行），但修复
  走的是补向量路线，不依赖重传；后续若要重传，先移植 valorant 脚本的
  串行逻辑。
