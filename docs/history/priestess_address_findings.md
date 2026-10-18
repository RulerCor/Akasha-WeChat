# 普瑞赛斯（Priestess）对博士的称呼 —— 调研发现

**调研范围**：普瑞赛斯在《明日方舟》主线/活动剧情中如何称呼玩家角色「博士」；是否存在「预言家」这一称呼及其使用场景。
**调研者**：子代理（address-focused subagent）
**日期**：本次会话

---

## 一、核心结论（先给答案）

**「预言家」不是普瑞赛斯对博士的当面称呼，而是博士本人所属前文明研究团队的"代号"。**

分三层说清楚：

1. **「预言家」的性质 = 团队代号（codename），不是普瑞赛斯专用的爱称。**
   博士自己在剧情中明确说：别人更习惯叫他的团队代号「预言家」。
   > "Doctor? Not many people call me that. They prefer my team codename—'Oracle'."
   —— **BB-ST-3**（SideStory「巴别塔」）

2. **普瑞赛斯当面称呼博士时，游戏使用的是玩家昵称模板 `{nickname}`，而不是「预言家」，也不是「博士」。**
   这是本次调研最重要的发现。在普瑞赛斯与博士的前文明对话中（BB-ST-2、14-19 回忆段、15-17 前文明闪回、15-8），凡是普瑞赛斯直接喊博士的地方，文本一律写作 `{nickname}`（即玩家自己的名字）。经统计：BB-ST-2 出现 4 次、14-19 出现 13 次、15-17 出现 7 次。

3. **普瑞赛斯在少数场合确实当面称他为「博士」（Doctor）——但那是在现文明时间线/博士失忆之后。**
   14-19 中普瑞赛斯有一句直接喊话：
   > "Doctor! Your mind's wandered off again."
   （"博士！你又走神了。"）

**因此，任务中"普瑞赛斯称博士为「预言家」而非「博士」"这一假设，根据现有证据是不成立的**：
- 在**前文明场景**中，剧本层面把该角色标为 Oracle（预言家），但普瑞赛斯**口头的**称呼是 `{nickname}`；
- 在**现文明场景**中，普瑞赛斯口头称他为「博士」。

---

## 二、逐条证据（含出处）

### 证据 1｜「预言家」= 团队代号（最强单点证据）

**出处**：BB-ST-3（SideStory「巴别塔」）
**场景**：特蕾西娅在意识中遇到博士残存的情绪碎片。
**原文（英文版剧本）**：

```
{{sc|???|Doctor?
Not many people call me that. They prefer my team codename—"Oracle".}}
{{sc|Theresa|...Oracle...
So you're the one Kal'tsit believes in.}}
```

**说明**：说话者先被标为 `???`，说出这句话后剧本即改标为 `Oracle`。这是全游戏中把「预言家」定性为**代号**最直接的一句台词。

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=BB-ST-3&prop=wikitext&format=json`
（本地留存：`priestess_research/wgvx_BB-ST-3.wikitext` 第 85–87 行）

---

### 证据 2｜凯尔希明确说明「预言家」是博士的"曾用代号"

**出处**：15-17（第十五章「离解复合」）
**原文（英文版剧本）**：

```
{{sc|Kal'tsit|Dr. {nickname}, you ought to already know that Originium ... was finally completed by Oracle and Priestess.
'Oracle' was your previous code name.}}
```

**中文对应**（据 CN 名称对照表）：凯尔希对博士说，源石由「预言家」与「普瑞赛斯」共同完成，**「预言家」是你曾经的代号**。

**注意**：这句话是**凯尔希**说的，不是普瑞赛斯说的；且凯尔希同时用了 `Dr. {nickname}` 与 `Oracle` 两个称谓，正好体现"博士"是现用称呼、"预言家"是旧代号。

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=15-17/Story&prop=wikitext&format=json`
（本地留存：`priestess_research/wgv_15-17_Story.wikitext` 第 118 行）

---

### 证据 3｜官方中英日韩名称对照表（权威佐证）

**出处**：Arknights Terra Wiki「Doctor」条目 infobox，字段 `othername`：

```
*{{Names|text=Oracle|cn=预言家|tw=預言家|jp=預言者（オラクル）|kr=예언가}}
*Ghost/Evil Spirit of Babel
```

同页 `realname` 字段注明：

> "The Doctor's name is assumed to be the player's nickname; the Arknights Terra Wiki will use "{nickname}" when referring to the Doctor's name in operation stories and interludes."

**结论**：
- 「预言家」的官方英文是 **Oracle**，日文 **預言者（オラクル）**，韩文 **예언가**；
- 博士的**真名就是玩家昵称**，剧本中以 `{nickname}` 占位。

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=Doctor&prop=wikitext&format=json`
（本地留存：`priestess_research/wgv_Doctor.wikitext` 第 11 行、第 58 行）

同页第 58 行进一步说明：

> "In their time, the Doctor was mainly known as '''Oracle''', a codename from their research group.<ref>[[BB-ST-3]]</ref>"

即：**在（前文明）那个时代，博士主要被称为 Oracle——这是来自其研究小组的代号。**

---

### 证据 4｜普瑞赛斯称呼博士一律用 `{nickname}`（前文明场景）

**出处 A**：BB-ST-2（SideStory「巴别塔」，前文明场景）
**场景**：普瑞赛斯把 Ama-10 诞生时的极化波形做成"礼物"送给博士。

```
{{sc|Priestess|I prepared a gift for you, {nickname}.
What do you hear?}}
...
{{sc|Priestess|Oh... I knew you'd like it, {nickname}.}}
...
{{sc|Priestess|Come walk with me, before the silence comes.
I hope... we'll get to see this world's future with our own eyes together, {nickname}.}}
```

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=BB-ST-2&prop=wikitext&format=json`
（本地留存：`priestess_research/bb_st2.wikitext` 第 15、17、21 行）

> ⚠️ 以 `{nickname}` 结尾时的标点：原文写作 `{nickname}.`，即模板已含句读位置。此处照抄英文版剧本原始写法。

---

**出处 B**：15-17 前文明闪回（"灰色闪回"支线）
**场景**：普瑞赛斯与博士在罗德岛号舱室内讨论源石与休眠。

```
{{sc|Priestess|You seem a bit down, {nickname}.
Care to share the reason with me?}}
...
{{sc|Priestess|I've never forgotten our matter of debate, {nickname}. We shouldn't hold any reservations towards each other.}}
...
{{sc|Priestess|I'll wait, {nickname}, until you make the choice to stand by my side.}}
{{sc|Priestess|Take it easy, {nickname}. Your recent observations must have exhausted you.}}
{{sc|Priestess|Goodnight, {nickname}.
Until the end of time, when we have transcended the silence of the universe.
I will wait for you in that world.}}
```

**关键**：同一场景中博士的台词说话人标签是 `{{sc|Oracle|...}}`，而普瑞赛斯开口时用的是 `{nickname}`。
**即：剧本层面标"Oracle（预言家）"，普瑞赛斯口头却叫玩家昵称。**

该场景的 `chars` 声明：
```
|chars = {{si|mode=char|Doctor|Oracle}}{{si|mode=char|Priestess}}
```
意为"Doctor 角色，在此显示为 Oracle"。

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=15-17/Story&prop=wikitext&format=json`
（本地留存：`priestess_research/wgv_15-17_Story.wikitext` 第 152 行起）

---

**出处 C**：15-8（第十五章）
**场景**：博士与阿米娅在"文明的存续"（黑冠）留存信息中看到普瑞赛斯。

```
{{sc|Priestess|(Unknown language) ... Besides, I'm sure you won't say no to me, {nickname}.}}
```

同场景 `chars`：`{{si|mode=char|Doctor|icon=Doctor DM|Oracle}}{{si|mode=char|Priestess|unknown=true}}`

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=15-8/Story&prop=wikitext&format=json`
（本地留存：`priestess_research/wgv_15-8_Story.wikitext` 第 5、16 行）

---

### 证据 5｜普瑞赛斯当面称他「博士」（现文明 / 14-19）

**出处**：14-19（第十四章「慈悲灯塔」）
**场景**：博士攻入源石"阿喃那"的内化宇宙后，普瑞赛斯唤醒并与之交谈。

```
{{sc|Priestess|Doctor!
Your mind's wandered off again. It seems you have a penchant for speaking in that alien language.}}
```

**说明**：这是普瑞赛斯**明确以「博士」称呼主角**的一句台词。该场景还有大量 `{nickname}` 用法（共 13 处）。
同场景普瑞赛斯的重逢台词（可用作报告素材）：

```
{{sc|Priestess|Don't tell me that you've even forgotten my name just because you've had a big nap.
Come on, say my name again. The database will analyze all of your voice data.}}
```

以及她自报家门（转述初次见面）：

```
{{sc|Priestess|"My name is Priestess, a linguist. I am researching the final sound waves emitted by planets as they die.
I like quietly spending my time alone, but I also wanted to find someone to explore the universe with."}}
```

**来源 URL**：`https://arknights.wiki.gg/api.php?action=parse&page=14-19/Story&prop=wikitext&format=json`
（本地留存：`priestess_research/wgvx_14-19_Story.wikitext`）

---

## 三、中文侧佐证（非逐字剧本，但为中文权威设定页）

### 萌娘百科「普瑞赛斯」条目（中文，可正常抓取）
URL：`https://mzh.moegirl.org.cn/普瑞赛斯`

该页**通篇**在叙述前文明段落时使用「预言家」，现文明段落使用「博士」，与上述结论完全一致。摘其关键句：

> 「普瑞赛斯与预言家相熟，二人一同制造了Ama-10。为应对前文明将要面临的未知灾厄，普瑞赛斯和预言家将目光投向前文明的的供能项目"源石"上。」

> 「然而普瑞赛斯与预言家对源石的应用方向有分歧：预言家希望源石能成为未来新文明的助力与航标；普瑞赛斯却希望源石能同化全泰拉……普瑞赛斯将预言家安置在罗德岛号的石棺中。」

> 「第十五章离解复合的剧情中，博士和阿米娅看到了过去在罗德岛甲板上普瑞赛斯和预言家交谈的画面，其中预言家提到了他改进过普瑞赛斯研发的PRTS。」

**注意**：萌百是**叙述性**文字（编者视角），**不是**逐字台词。可作为中文命名习惯的权威佐证，但不能当作台词引用。

---

### 萌娘百科「博士」条目（中文）
URL：`https://mzh.moegirl.org.cn/博士(明日方舟)`

关键字段与脚注：

> 「别号：**"预言家"** [2]、刀客特、刀客塔、让人不快的人、巴别塔的恶灵……」

> 脚注 [2]：「**前文明时代的团队称呼**」

> 正文：「SideStory「巴别塔」中，博士是源石计划的参与者之一，**团队内称呼"预言家"**……」

**这是中文侧最有力的一句**：萌百明确指出「预言家」是**前文明时代的团队称呼**（即代号），而非普瑞赛斯个人对他的称谓。

---

### 萌娘百科「前文明」条目（中文）
URL：`https://mzh.moegirl.org.cn/前文明`

该页在"前文明人物"一节写作：「**预言家/博士**」，即明确标示二者为同一人的两个称谓。并引用了预言家录音中 BB-8 的一段话（**这是本报告能找到的、唯一带中文出处标注的成段引文**）：

> 「我相信它们。相信你，凯尔希。
> 凯尔希……我时间不多了。
> 去寻找生命的痕迹，去寻找希望与未来。
> 凯尔希……自己去得出答案吧。
> 去找到你自己。」
> ——**预言家，BB-8 终局倒计时 行动后剧情**

**注意**：这段是**预言家（博士）**对凯尔希说的话，**不是**普瑞赛斯说的话，也不是普瑞赛斯对他的称呼。但它是本次调研中**唯一拿到"中文原文 + 明确出处"**的逐字引文，故列出。

---

## 四、明确未能核实的内容（⚠️ 重要）

以下各项**本次调研未能取得**，不得在报告中当作已证实内容引用：

1. **普瑞赛斯中文台词的逐字原文** —— 未能取得。
   - PRTS（prts.wiki）全线 403（主页、api.php、`?action=raw` 均 403），与任务提示一致。
   - `ak.mooncell.wiki`（PRTS 备用域名）无法解析/连接（curl 返回 000）。
   - 萌娘百科的 `api.php` 被禁用（`action-notallowed`），且章节页（如 `/15-17`、`/离解复合`）返回的是 **JS 外壳页面**，正文需 JavaScript 渲染，纯 curl 抓不到内容。
   - bilibili 明日方舟 wiki（wiki.biligame.com/arknights）API 可用，但**不收录完整剧情文本**（只有关卡页与少量条目），搜索「普瑞赛斯」仅命中 7 条无关条目。
   - NGA（ngabbs.com）返回「请先登录」拦截页；百度贴吧返回「百度安全验证」。
   - 百度百科返回 4.7KB 反爬占位页，无正文。
   - `r.jina.ai` 代理无法连接（000）。

2. **因此，本报告中的英文引文均为 arknights.wiki.gg（Arknights Terra Wiki，EN 官方剧本转录）原文。**
   中文措辞（如"博士！你又走神了"）为**我的翻译**，已在文中明确标注，**不是**游戏中文原文。请勿当作中文官译引用。

3. **普瑞赛斯是否曾在**任何**场合用「预言家」二字当面称呼博士 —— 未能证实，且现有证据**倾向于否定**（前文明场景她用 `{nickname}`；现文明场景她用"Doctor"）。
   若要彻底证否，需核查全部含普瑞赛斯的剧情节点（14-19、15-8、15-17、BB-ST-2、BB-ST-3、孤星、众生行记、16/17 章），本次仅覆盖其中主要节点。

4. **`{nickname}` 在简中服的最终渲染结果** —— 未直接验证。
   根据 Terra Wiki 的说明，它渲染为**玩家在游戏内设定的昵称**；但简中服是否在部分语境下回退为"博士"，本次**未能实测**。这一点会直接影响报告的精确表述，建议以实际游戏截图复核。

5. **PV4 解密「预言家录音」的中文原文** —— 未取得完整逐字稿。
   萌百「前文明」页只给出了中文译文片段（见上），英文版（`The Custodians` / `The Forsterer` / `The Security` / `The Lumberer` 四段）在萌百页面上也有收录，但**中英对应关系与是否为官方简中原文，未能核实**。

6. **「团队内称呼预言家」的原始出处（BB-ST-3）中文原文** —— 未取得，仅有英文版与萌百的转述。

---

## 五、可用作报告的稳妥表述建议

若要写进中文报告，建议采用如下**有证据支撑**的措辞：

- ✅ 「预言家」（Oracle）是博士前文明时期的**团队代号**，官方中英日韩对照为：预言家 / Oracle / 預言者（オラクル）/ 예언가。（证据 1、2、3）
- ✅ 在涉及前文明的剧情（「巴别塔」BB-ST-2/BB-ST-3、第十五章 15-8 / 15-17）中，剧本以 **Oracle（预言家）** 标注博士。（证据 1、4B、4C）
- ✅ 普瑞赛斯在前文明场景中对博士的**口头称呼**为**玩家昵称**（剧本占位符 `{nickname}`），而非"预言家"。（证据 4A、4B、4C）
- ✅ 在第十四章「慈悲灯塔」14-19 的内化宇宙对话中，普瑞赛斯当面称他为**「博士」（Doctor）**。（证据 5）
- ✅ 中文侧的萌娘百科明确将「预言家」界定为**"前文明时代的团队称呼"**。（第三节）

- ❌ 不建议写：「普瑞赛斯称博士为预言家」。**现有证据不支持，且倾向于相反。**
- ⚠️ 如必须使用"普瑞赛斯叫他预言家"这类表述，应加限定语并说明争议，或先补做简中原文核查。

---

## 六、本次留存的本地文件（工作区）

| 文件 | 内容 |
|---|---|
| `priestess_research/wgvx_BB-ST-3.wikitext` | BB-ST-3 英文剧本（证据 1） |
| `priestess_research/wgv_15-17_Story.wikitext` | 15-17 英文剧本，含前文明闪回（证据 2、4B） |
| `priestess_research/wgv_15-8_Story.wikitext` | 15-8 英文剧本（证据 4C） |
| `priestess_research/wgvx_14-19_Story.wikitext` | 14-19 英文剧本（证据 5） |
| `priestess_research/bb_st2.wikitext` | BB-ST-2 英文剧本（证据 4A） |
| `priestess_research/wgv_Doctor.wikitext` | Doctor 条目，含名称对照表（证据 3） |
| `priestess_research/wgv_Priestess.wikitext` | Priestess 条目 |
| `priestess_research/raw/moegirl_priestess.txt` | 萌娘百科「普瑞赛斯」正文 |
| `priestess_research/raw/moegirl_e4bd4e4c.txt` | 萌娘百科「博士」正文 |
| `priestess_research/raw/mg_precivil.txt` | 萌娘百科「前文明」正文 |

> 注：`priestess_research/` 目录下另有部分文件（如 `wg_1419.txt`、`si.json`、`huiji.html` 等）由**并行工作的其他子代理**创建，非本次调研产物；本次复用其中的 EN 剧本数据并已重新校验。
