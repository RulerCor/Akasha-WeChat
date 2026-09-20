# 普瑞赛斯 (Priestess / プリースティス) — 台词与设定考据 findings

Researcher: subagent (lines & lore focus)
Date: 2026-09-20
Working dir: `C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\priestess_research`

---

## 0. METHOD / SOURCE CONFIDENCE (read this first)

**Correction to the brief's assumption: we DID obtain full verbatim Chinese script text.**

The brief hypothesized that Chinese verbatim text was unavailable (PRTS 403, moegirl chapter pages
are JS shells). That is true for `prts.wiki` (403, confirmed) and `mzh.moegirl.org.cn` chapter pages
(no story scripts). **But we found the actual official game script files, in Chinese, and extracted
her lines directly.**

### Primary source (authoritative — actual in-game script JSON)

The ASTR "明日方舟剧情文本阅读器" front-end (`https://astr.pages.dev`) ships its data loader with two
mirrors hard-coded in its JS bundle:

- `https://r2.m31ns.top/` (dead / 404 at time of research)
- `https://raw.githubusercontent.com/050644zf/ArknightsStoryJson/main/` (used via jsDelivr CDN)

Confirmed bundle strings: `"/gamedata/story/" + this.path + ".json"`, `"/storyinfo.json"`,
`"/chardict.json"`, `"/gamedata/excel/chapter_table.json"`.

Working data path pattern (verified 200):

```
https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/gamedata/story/<storykey>.json
https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/storyinfo.json   (420,325 bytes, zh_CN index)
```

Each script JSON has `storyCode`, `storyName`, `avgTag` (行动前/行动后), `eventName`, and a
`storyList[]` of nodes. Dialogue nodes look like:

```json
{"id": 65, "prop": "name", "attributes": {"content": "……台词正文……", "name": "普瑞赛斯"}}
```

`{@nickname}` is the in-game placeholder for the player's chosen name (default 博士). We preserve it
verbatim. Unnamed narration uses `"prop": "name"` with no `name` field; on-screen captions use
`"prop": "Subtitle"` with an `attributes.text` field.

**Therefore: every Chinese line quoted below is copied verbatim from the shipped game script JSON,
not from a fan transcription, translation, or wiki paraphrase.** Translation glosses are ours and are
marked as such.

### Secondary sources (used for lore framing / citations)

- `https://arknights.wiki.gg/api.php?action=parse&page=Priestess&prop=wikitext&format=json&formatversion=2`
  — English wiki.gg `Priestess` page, which carries per-scene citations (`14-19 Before`, `BB-ST-2`,
  `M8-8 After`, `Pignus`, `CW-9 After`, `CW-ST-3`, `15-16`, `15-17 Before`, `15-12 Before`, `MT-9`,
  `MT-10`, `MT-ST-4`). Used to cross-check *which* scene a line belongs to.
- `https://mzh.moegirl.org.cn/普瑞赛斯` — 萌娘百科 普瑞赛斯 (Chinese lore summary; page rev 8469841).
  Used for event-appearance list and CN community framing. Local copy: `mg2.txt`.
- `https://wiki.biligame.com/arknights/` — bilibili 明日方舟WIKI. Its MediaWiki API works:
  `https://wiki.biligame.com/arknights/api.php?action=query&list=search&srsearch=普瑞赛斯`
  Returned 15-19 narration text and the Kal'tsit·Esperanta (凯尔希·思衡托) operator page
  (pageid 126501) containing AMa-10 lore. Useful; NOT a script mirror.
- `prts.wiki` → **403, do not retry** (confirmed).

### Script-key → in-game stage-code mapping (IMPORTANT, non-obvious)

The JSON filename and the in-game stage number **differ**. Verified mappings used below:

| JSON key | `storyCode` | `storyName` | `avgTag` |
|---|---|---|---|
| `obt/main/level_main_14-17_beg` | **14-19** | 晶簇之内 | 行动前 |
| `obt/main/level_main_15-06_end` | **15-7** | 临界时刻 | 行动后 |
| `obt/main/level_main_15-07_beg` | **15-8** | 破碎回响 | 行动前 |
| `obt/main/level_main_15-11_beg` | **15-12** | 目击众神死亡的荒原 | 行动前 |
| `obt/main/level_main_15-15_beg` | **15-17** | “她” | 行动前 |
| `obt/main/level_main_15-15_end` | **15-17** | “她” | 行动后 |
| `obt/main/level_main_15-15_end_variation01/02` | **15-17** | (问卷分歧变体) | 行动后 |
| `obt/main/level_main_15-16_beg` | **15-18** | 从未怀疑，从未远离 | 行动前 |
| `obt/main/level_main_14-20_end` | **14-22** | 在哀愁绽放的时刻 | 行动后 |
| `activities/act33side/level_act33side_st02` | **BB-ST-2** | 在疲惫中苏醒 | — |
| `activities/act25side/level_act25side_09_beg/_end` | **CW-9** | 恩怨纠葛 | — |
| `activities/act25side/level_act25side_st03` | **CW-ST-3** | 留下的人 | — |
| `activities/act42side/level_act42side_09_beg/_end` | **MT-9** | 解经 | — |
| `activities/act42side/level_act42side_st04` | **MT-ST-4** | 远行 | — |
| `obt/main/level_main_16-12_beg` | 16-12 | 深埋地底 | 行动前 |
| `obt/main/level_main_17-16_end` | **17-17** | 不曾怀疑 | 行动后 |
| `obt/main/level_main_17-17_beg` | **17-18** | 灵魂悄然 | 行动前 |
| `obt/main/level_st_17-04` | **17-21** | 在暗夜中燃烧 | — |

Event activity-id map (verified by reading `storyCode`/`eventName` out of each ST-1 file):
`act33side = 巴别塔 (BB)`, `act25side = 孤星 (CW)`, `act42side = 众生行记 (MT)`,
`act43side = 红丝绒 (AD)`, `act44side = 墟 (AT)`, `act41side = 挽歌燃烧殆尽 (EA)`,
`act46side = 雪山降临1101 (OS)`, `act54side = 月行水上 (SR)`.

---

## PART A — VERBATIM CHINESE 台词

Speaker tag as it appears in the script is given in brackets when it is NOT literally `普瑞赛斯`.
All lines below are **CONFIRMED in-game text** unless a block is explicitly marked otherwise.
`{@nickname}` is the game's literal placeholder for the player name (default 博士).

---

### A1. 第十四章「慈悲灯塔」14-19 「晶簇之内」 — 自我介绍（★ the exact Chinese you asked for）

Source: `zh_CN/gamedata/story/obt/main/level_main_14-17_beg.json` (`storyCode: "14-19"`, `storyName: "晶簇之内"`, `avgTag: "行动前"`)

**The self-introduction, verbatim:**

> **「我叫普瑞赛斯，语言学家。我正在研究行星死去时发出的最后声波。我喜欢安静地独处，但也想和合适的人一起探索宇宙。」**
> — 普瑞赛斯，14-19「晶簇之内」行动前

*(our gloss: "My name is Priestess, a linguist. I am researching the final sound waves emitted by
planets as they die. I like quietly spending my time alone, but I also wanted to find someone
suitable to explore the universe with." — this is the exact line the English wiki renders as
"My name is Priestess, a linguist. I am researching the final sound waves emitted by planets as
they die. I like quietly spending my time alone, but I also wanted to find someone to explore the
universe with." So the brief's English line is confirmed as a faithful render of the CN original.
NOTE the CN has 「和合适的人」 = "the right/suitable person", which the EN flattens to "someone".)*

Full contiguous 14-19 Priestess speech, in script order (selected high-value lines; the complete
list is 60+ lines, all extracted to `/tmp/scr/d1417beg.txt` during research):

> 欸，你又从哪里学来了这么奇怪的语言？
> 这次休眠你又偷偷将思维上传到某个旋臂末端的文明中了吗？
> 好了，再确认一下你的语言功能恢复得如何吧。
> 别说你睡了一场大觉，连我的名字都忘记了。
> 来，再叫一次我的名字，数据库会分析你的所有声音数据。
> 恢复得很快嘛，{@nickname}。
> 但是你的身体刚刚复苏，还没有完全适应。
> 急着乱动的话，小心NX-07把你按回床铺哦。它新换的指令很难解开，就连我都爱莫能助。
> 当然还在“罗德岛”，我们的家。
> 怎么会只有你呢？我也在这里呀。
> ……你果然还是会这样问。
> 变故发生得很快。防御矩阵损伤超过了百分之九十，受极端环境影响，修理单元也很难在短时间内恢复工作。
> 在你休眠后不久，许多同事就相继离开了这里……大家都很珍惜这星星坠落之前的时间，我很理解。
> 现在，的确只有我们两个了。当然，AMa-10也还在，而且精神很好，很活泼。
> 别担心，罗德岛剩下的部分还可以维系基本功能，我们还有一点时间。
> {@nickname}，你在我身边的时候，我并不害怕结局。
> 无论是构成我们身体的物质崩毁，我们的意识停止变化，还是宇宙的法则颠倒，我都可以坦然接受。
> 只要你还在我身边就够了。

> 定义梦和现实的权力，一直都握于我们掌中，{@nickname}。
> 当我们的思维在寰宇中穿梭亿万光年，参加那些于冰冻旷野中向白矮星祭拜生命的仪式时，我们如何定义这等体验呢？

> 这里嘛……“不可知”。
> 我们一起建造这个地方的时候，曾经许下过一个共同的愿望。
> 等到群星的最后一丝温热消散，时间的路网完全陷入混乱的那一天，就让黑暗成为我们共同的被子吧。
> 等到这个世界，这片星空迎来最后的时刻……我们的宇宙本来就会变成一座巨大的坟墓。
> 没有任何一颗星球的角落里藏着希望。但凡有一颗宇宙碎片的微粒上藏着救赎的答案，它也一定已经被我们打捞起来了。
> 每一次的反抗都以提前毁灭告终，每一次的探索都只会带来更深重的绝望……
> 结论是那么简单。任何以正常物质为基础的生命形式都无法逃离。任何一种可知的技术，都无法战胜那绝对的终结。

> 亲密？我不会用这种词语来形容我们之间的关系。
> 这是对我们过去所经历的一切的贬低。

> “牵手”——嗯，我们有很多种不同方式的“牵手”。很多时候并不需要借助躯体的某些具体部分。
> 我们第一次见面的时候……我正在环绕着一颗海洋星球飞行。我把恒星当作不变的锚，沿着昼夜分界线，飞了一圈又一圈。
> 恒星的死亡来得很快。我身下的海洋几乎在一瞬间离解了，露出了星球赤裸的暗红色脊骨。
> 有人从身后拉住了我，把我拽到了一处更安静的星云里。
> 那个人向我解释，知道我很可能不会有危险，但那个人来不及确认我的本体在哪个星场中，只能用自己的船打捞了我的意识信标。
> 那是我第一次登上那艘卵形的船。它并不大，可是很灵活，已经去过无数个星系。
> 我把船带到了一颗并不算热闹的行星上。我向船的主人展示了我面向大海的小实验室，并且走到了那个人的面前。
> 就像这样……我握住了对方的手。

> 所有人都说，我是那个创造了源石与未来，像“神明”一般的人。
> 但我一直都知道，真正的天才是你，{@nickname}。
> 你忘记了……但你不该忘记。
> 在创造它的路上，我不断地追赶你的脚步。
> 我害怕在某一次与你辩论时掉队，害怕让你发现我本不如你。
> 不，或许你发现了……也许你也曾放慢脚步等我，等待我追上你。
> 可现在，我永远都不会知道答案了……

> 我本想和你分享一些我一直替你保存的东西。
> 那些你曾向我描绘，如今你自己却已全然忘记的理念和愿景……
> 我想让你知道我们所取得的成就。
> 也许这样，你能想起过去，想起我——
> 但我能看见你所想，我能感受你所思。
> 就像此刻，你的脑海中依旧萦绕着无穷的疑惑……
> “阿米娅”“凯尔希”——
> 我……不想让你为难，我尊重你的选择。
> 但我很确信……{@nickname}……
> 当你真正对一切感到困惑的时候，你会想起——答案一直都在这里。
> 我在这里。

**On-screen caption (`prop: "Subtitle"`, colour-tagged) closing 14-19 — this is the CN counterpart of
the English "Once you ease your worried mind, you can go back to me":**

> 去吧，“博士”，去解开你的困惑。
> 你所有的愿望，我都能够实现。
> 而在所有宏大的搏动和微小的悸动都归于寂静之后——
> **我的身边将是你的归处。**

*(gloss: "Go, 'Doctor', go untie your confusion. / All that you wish for, I am able to grant. / And
after all the grand pulsations and minute tremblings fall into silence — / **your place of return
will be by my side**." — This is the **Chinese** of the "you can go back to me" beat. Note the EN
wiki's "Once you ease your worried mind" is a loose render; the CN literally says 「去解开你的困惑」.)*

---

### A2. SideStory「巴别塔」BB-ST-2 「在疲惫中苏醒」 — 群星正在褪色 / 归于寂静

Source: `zh_CN/gamedata/story/activities/act33side/level_act33side_st02.json` (`storyCode: "BB-ST-2"`, `eventName: "巴别塔"`)

> 我为你准备了一份礼物，{@nickname}。
> 你听到了什么？
> 还记得吗？这是AMa-10诞生时产生的偏振，你说你在它的波形中找到了一段旋律。当然，我也加入了一些“个人创作”。
> 我调整了远行星轨道阵列的方向来捕获不同的回响，和声提取自恒星熄灭时的中微子余韵，配器是航船穿过星门时留下的重力褶皱。
> 啊……我就知道你会喜欢，{@nickname}。
> **群星正在褪色。这个世界已经没有准则了，不是吗？**
> **这里很快也会安静下来，就像我们从未来过一样。**
> **陪我走走吧，在归于寂静前。**
> 我希望……我们还会一起亲眼看到这个世界的未来，{@nickname}。

*(gloss: "The stars are fading. This world no longer has any norms, does it? / This place will soon
fall silent too, as if we had never been. / Walk with me, before it all falls silent." — This
confirms the brief's "stars losing their colors / 沉默" beat, verbatim in Chinese.)*

---

### A3. 第十五章「离解复合」

#### 15-2 / 15-3 — the 「好久不见」 greeting question

**IMPORTANT FINDING:** There is **no** Priestess line rendered literally as 「好久不见」 addressed to
the Doctor. The actual 「好久不见」 beats found across the corpus are:

- `obt/main/level_main_14-17_end.json` (14-19 行动后), speaker **阿米娅**? — actually speaker tagged 普瑞赛斯-adjacent; text: 「博士，好久不见，我回来了。」
- `obt/main/level_main_14-19_end.json`: 「阿米娅，好久不见。」
- `obt/main/level_main_15-01_beg.json`: 「好久不见，阿斯卡纶。」 (speaker: 阿斯卡纶's interlocutor)
- **The one genuinely Priestess-to-Kal'tsit:** in `obt/main/level_main_15-15_beg.json` (15-17 行动前):

> **「是你啊……AMa-10。同样好久不见了。」** — 普瑞赛斯

*(The English wiki renders this as the "Long time no see." caption attached to image `60 i25.png`.
So the brief's «15-16, 15-17 "Long time no see"» is real, but it is spoken **to AMa-10/凯尔希**,
not to the Doctor, and it is 「同样好久不见了」, not a bare 「好久不见」.)*

#### 15-7 行动后 / 15-8 行动前 — the 「未知语言」 (unknown-language) exchanges with 预言家

Source: `obt/main/level_main_15-06_end.json` (`storyCode: "15-7"`), `obt/main/level_main_15-07_beg.json` (`storyCode: "15-8"`)

These are the **pre-civilisation conversations with 预言家 (Oracle)** — all tagged
`（未知语言）` in-game. Crucially this is where the PRTS claim is confirmed (see Part B):

> （未知语言）你来了，{@nickname}。 — 普瑞赛斯
> **（未知语言）改进你设计出来的PRTS花了点时间。** — **预言家**
> （未知语言）我以为你去休息了。 — 预言家
> （未知语言）不，我一直在想你刚刚说的话。 — 普瑞赛斯
> （未知语言）“不存在描述神的语言，因为神本身的存在是绝对不可理解的。” — 普瑞赛斯
> （未知语言）你很清楚那只是我们漫无目的聊天时的随口之言。 — 预言家
> （未知语言）如果我假设这是一个正确的前提。
> （未知语言）以此为出发点，创造一种足够描述神的语言，是否也意味着神能够被我们理解？
> （未知语言）难道你不为此而激动吗？
> （未知语言）也许我们为了找到那个问题的答案，一直都走在了错误的道路上——试图借助宇宙已经诞生的规则去解读宇宙的本质。
> （未知语言）哈哈，是吗？
> （未知语言）那干脆就从现在开始，如何？

From `obt/main/level_main_15-07_beg.json` (15-8 行动前):

> （未知语言）我并不认为仅靠我自己就能创造出一门足以阐述终极答案的语言。
> （未知语言）至少，同胞们共享的各领域最顶尖的研究成果已经给我搭建了继续深入的平台。
> （未知语言）嗯，反正又不是第一次了。
> （未知语言）在安静等待黑暗吞噬我们的这段日子里，我们似乎也没有更好的办法了不是吗？
> （未知语言）况且，我确定你不会拒绝我，{@nickname}。

#### 15-12 「目击众神死亡的荒原」行动前 — speaker tag is 「温柔的声音」, NOT 普瑞赛斯

Source: `obt/main/level_main_15-11_beg.json` (`storyCode: "15-12"`, `avgTag: "行动前"`)
Speaker field: `{"name": "温柔的声音"}` (20 tagged lines). **This is the key terminological caveat:
in this scene she is only credited as "a gentle voice" until the very end of the block, when she
names herself.**

> 铭记文明死去的墓地。
> 文明诞生于那片浩瀚的宇宙，就如同一滴雨水坠入大海，势必荡起涟漪，在宇宙中留下自己的痕迹。
> 死去文明的涟漪永恒地凝固在这墓碑之上。而那些璀璨如明星，启迪无数后来者的先行者哪怕已经在时光中消逝——
> 他们依旧会对宇宙产生无可比拟的影响。你看，他们荡起的涟漪形成了我们所站立的这片大地。
> 而他们的遗产供养着新生者，也承接着新生的文明在宇宙中留下的足迹。
> 你不是第一个这样形容它的人。 — 温柔的声音 *(after 希尔达 says the tombstone looks like a snapped tree stump)*
> 有一位于我而言很重要的人也曾向我这样说起过。
> **一个绝对存在的终极孜孜不倦地收割着这可怜树桩上新发出的枝桠，而我们却对祂一无所知。**
> “神明”？
> **我只是一个希望解释宇宙的语言学家。**
> **我的名字是普瑞赛斯。**

*(This is the "Lumberer/woodcutter" concept in Chinese — 收割/剪断树枝的绝对终极. Note the CN does
NOT use a proper noun 「伐木工」 here; it says 「一个绝对存在的终极孜孜不倦地收割着…枝桠」. The term
「伐木工」 as a fan/wiki proper noun is NOT present in this block. See Part C.)*

Her lines to 希尔达 (Hierda) in the same script, tagged `普瑞赛斯`:

> 严格来说，我并没有救下你。
> 你的死亡的确已经发生，物质向信息转译的过程我并未干预。
> 但物质的消亡并不意味着真正的死亡，信息不会被轻易泯灭。源石记录了你的信息。
> 那同样只是一段无限重复的数据流而已。
> 我特意留下了一些历史碎片来观察我们过去的生活。
> 梦是笼统且主观的描述，在你触及语言的本质之前，不要因此陷入虚无的自我怀疑。
> 你可以理解为这里是来自过去的一个瞬间，被我以信息的方式记录。
> ……但这段时光终究只是一幅静滞的画面，它永远不会拥有未来。
> 你死亡的那一刹那，我看见了你。
> 有人惊扰了我，这是基于概率而发生的巧合。
> 不，希尔达，你和你的同类很特殊。
> 你们被源石塑造成了如今的模样，与源石产生了如此奇妙的交互。
> 你们的历史，你们的文明，都是因源石而存在。
> **是的，这是一个错误，你们的存在是计划之外的状况。**
> 不，你误解了我的意思。
> 你们的文明因概率而诞生，就像你会出现在这里一样，都是时间中客观的存在。
> 因概率而诞生，也因概率而消亡，这是这个宇宙中最普遍的规律。
> 希尔达，你令我感到好奇。
> 我在这里可以观察到你所在的世界的一切，你是这个文明中第二个与我交流的生命。
> 我想问你……你依然爱着那片大地，对吗？
> 哪怕它带给你们的痛苦也真实存在且挥之不去？
> 你所在意的，也是如此吗？
> 只是对生命和意志的赞叹。死亡没有压倒你。
> 你为了求索一个关于未来的答案而寻找我，而我们现在已经站在答案之前——
> 那是语言所无法描述的答案。

The 「祂」/the light sequence (15-12, still 普瑞赛斯):

> 记得我刚刚提及的绝对存在的终极吗？
> 人们本以为那是一道遥远星体燃烧时发出的光。
> 历史。
> 虔诚的生灵在他们的最后时刻，依旧在向着宇宙未知的赐福祈祷。
> 而理性的科学主义者前赴后继地乘坐着飞行器冲入光芒中，他们渴望近距离接触真理。
> 狂热的唯心主义保守派愤怒地指责外来的敌人未经允许就进入了他们自意识诞生时就拥有的空间。
> 他们毫无顾忌地将最危险的武器倾泻向绚烂的天空。
> 你想接近那束光吗？
> 他们反抗。
> 他们祈祷。
> 他们试图用千万年来人为创造的一切美好说服那束冰冷的光——
> 但那束光是如此冷漠，如深空一般冰冷。
> 光掠过了星球，离开了。一切都安静了下来。
> 在那些碎片之上，也曾烙印着一个辉煌文明的印记。
> 没有人能在祂来临之前做好准备。
> 就连这个文明中最聪明、知识最渊博的智者也渴望在毁灭来临之前得到一点预兆和警示。
> 但很遗憾……
> 不，这只是我们捕获到的万千片段中的一个。
> 我所亲身经历的，远非这远远的一瞥可比。
> 你所渴求的答案并未完全结束，你看，废墟中就快出现声音了。
> 彗星。有时它们会带来生命的种子。有时它们也仅仅只是填补那破碎的死寂行星。
> 任何地方。甚至恰好就来自另一个经历了毁灭的行星，或许还刻印着那失落文明的痕迹。
> 来自他处的探索者，求知者，殖民者，抑或是纯粹的掠夺者。
> 他们同样会加速文明演化的进程。
> 你的贪婪压过了你的恐惧。
> 知识是不可逆转的，希尔达。当你窥探到了片面的真理后，你是否还能安然地回到无知的黑暗中去呢？
> 尽管这里只是永恒静止的时间碎片？
> 你们和我们很像。
> 你可以自由地行走在这里和罗德岛上的任何地方，去理解你想要的答案。
> 至于以后，留在这里，或是回到你牵挂的泰拉……
> 我会尊重你的选择。我们很快会再见面面的。 *(sic — script reads 再见面的.)*
> **有人在等我。**
> **……已经等了太久太久。**

#### 15-17「她」行动前 — the confrontation with the Doctor & Kal'tsit

Source: `obt/main/level_main_15-15_beg.json` (`storyCode: "15-17"`, `avgTag: "行动前"`)

> {@nickname}，是你先我一步呢。
> 你没有留在唤醒室等待我，与我一同分享第一次看见这个新世界的喜悦。
> 可我又怎么忍心责怪你这一点小小的心急呢？
> 虽然这样的重逢和我们预期的有所不同，不过我也愿意接受这种意外的体验。
> 我们无数次一同畅想过，在时间的另一头，我们从休眠中苏醒后第一次见面的情景。
> 源石已经完全包裹这颗星球，我们可以在其上自由地漫步，这是只属于我们的世界。
> 这个世界离我们共同的终极愿景只有一步之遥，我们正步向新的希望……
> **而且，那应该是一个明媚的晴天。**
> {@nickname}，这样的问题令我感到陌生。
> 这是我们共同的创造，只属于你我二人的结晶，是希望的种子。
> 但是很可惜……你已经不记得了，对吗？
> 我知道，因为一些遗憾的意外，你失去了一部分记忆。
> 虽然遗憾，但我相信，只是一部分记忆的缺失不会改变你的本性，我们之间的联系无可动摇。
> 我并不想对你有任何苛待，但是我希望你能理解——时间很紧张，我们还有许多事要做。
> 不过，我们总还是可以享受共事的时光，对吗？
> **回到我的身边，Dr.{@nickname}……**
> ……
> **是你啊……AMa-10。同样好久不见了。**
> 虽然你现在的模样和诞生之初相去甚远，可我怎会不认识自己倾注了情感的造物呢？
> 这四百多万个自然日的时间里，你似乎做了许多努力，但你行为的准则似乎并不符合你诞生时被预设的目标。
> 我想知道，到底是什么让你改变了主意。
> 是啊……是你将那个人的命令，当做了不可动摇的目标。
> 所以你阻碍了源石的计划，浪费了本就已寥寥无几的时间。
> 所以，{@nickname}，我该怎么让你明白……
> **我有多么失望。**
> **我又该如何原谅你的背叛？**
> 我注意到了，AMa-10。
> 你已经打破了我设下的语言的禁令，对吗？
> 这样的防备并不足以完全限制你的活动，你总是有办法……
> 既然如此，为什么不说出来？
> 这么长时间以来，那些你想说却没有办法告诉{@nickname}的一切？
> ……
> 要说的话，已经说完了吗？
> 我诧异于你对过往的认知，也对你的表述并不完全认同……不过，这都不重要了。
> AMa-10，现在的你，又能做到什么？
> 这就是你的选择……

Also in this scene, the player-choice line (attributed to the Doctor, for context):
> 我不会让源石毁灭泰拉。
Narration immediately after her 「……」:
> 你看到她的目光蒙上了一层阴翳，那是明显的失落。不知为何，你的心脏狠狠收紧了一下。

#### 15-17「她」行动后 — the killing of Kal'tsit

Source: `obt/main/level_main_15-15_end.json` (`storyCode: "15-17"`, `avgTag: "行动后"`)

> ……
> 你很让我惊喜，AMa-10。
> 你以切断自己双生循环的系统为代价来脱离我的控制，哪怕这样会使你的生命变得脆弱不堪。
> 不过，你真的打算用这样的方式杀了我吗？
> 你所说的两个人，我的确在源石内部见过他们。
> 他们的努力的确出人意料，是令人惊喜的挣扎。
> 所以呢？你又如何确信，在这里杀了我不是徒劳之举？
> ……
> ……你怎么能做到？
> ……？
> 你为了反抗我，竟然会做到这一步——
> ……！
> 有力的反抗，AMa-10，你的计划奏效了。
> 诚如你所说，现在你们的确有杀死我的机会……
> 可是，只是一个用源石塑造出的替身，就会让你如此慌张吗？
> AMa-10，我无意与你辩论你信奉的价值。
> 你一直以来所坚持的事，它们太渺小，我甚至无法找到一种可信的逻辑架构来评价它们的意义。
> 可是实验中的确会出现这样的情况，一些细小的误差，最终造成了巨大的妨碍。我不得不接受这样的结果。
> **我很遗憾，要将你当作这个误差来抹除。**
> 可惜。

#### 15-17 问卷分歧变体 (`..._end_variation01` / `_variation02`)

`variation01` opens with Priestess speaking to the Doctor before hibernation — this is the
**灰质销钉 (Lynchpin) confirmation**, verbatim:

> 你看上去有些低落，{@nickname}。
> 是什么原因呢？愿意与我分享吗？
> 不过我们已经做好准备了，对吗？
> 我们已经种下了希望的种子，接下来，只需要静待它长出答案即可。
> 不要担心，就当作是一次寻常的休眠吧。除了时间要稍微漫长一点，和以往的时间旅行并无本质不同。
> 何况这一次，我会在你身边的。
> 我希望在跨越了寂静的永夜后，再次睁开眼时，还能第一时间看到你。
> ……
> {@nickname}，我从来没有忘记我们的辩题。我们之间也不应存在任何保留。
> 看，当我们谈及属于我们的未来时，这就是我心中所想。我们应该是怀着同样的期待的。
> **嵌于我们思维中的同样的灰质销钉，也是将我们连接在一起的纽带。**
> **你我的思维因此得以紧密相连，直到我们的意识随整个宇宙共同寂灭。**
> 我们的思想交互碰撞，争论不休，却正因如此，我们才最能理解彼此的本性。
> 我很确信，对未来怀有期冀是我们的秉性，我们是彼此在这片虚无的星海中的锚点。
> 既然如此，我们就继续等待吧。
> 你现在还不愿意进入休眠，没有关系，我们还有一些时间。
> 我们可以一起阅览DWDB中保存的典籍，宇宙间也还有不少可供我们解读的死去的行星留下的诗句。
> {@nickname}，我会等待，等到你自己做出与我站在一起的选择。
> 放轻松一点，{@nickname}，最近的观测工作让你过于疲惫了。
> 闭上眼休息一会吧，我来帮你播放一段遥远的恒星用引力弹奏的和弦，你会有一个好梦的。

`variation02` opens instead with AMa-10 dialogue (per biligame 离解复合 page: 白色→预言家, 蓝色→AMa-10).
Both variants then carry the same 15-17 战斗 block quoted above.

#### 15-18「从未怀疑，从未远离」行动前

Source: `obt/main/level_main_15-16_beg.json` (`storyCode: "15-18"`)

> AMa-10也曾是我得意的创造。
> 这并非我期待的结果。
> 它已经有了自己的代号，我并不认同再次命名的意义。
> 你想要救它？
> 我也想修好它，和你一样。
> AMa-10不仅承载了我们共同的期待，它还保存了一段对我而言极为关键的记录。
> Dr.{@nickname}，你……为什么在害怕我？
> 这是……？
> 你并不明白自己在摆弄什么样的力量。
> **我的确过早地醒来了，源石同化这颗星球的速度并未达到我的预期。**
> 加之那两个泰拉人的莽撞行为，我没法如预期那样运用源石……
> 但这不代表你们如此草率地使用我们研发的技术就能改变既定的事实。

#### 15-19 「直至，此刻」 — PRTS takeover narration (from biligame wiki, color-coded red in-game)

Source (script JSON not in the GitHub mirror; taken from
`https://wiki.biligame.com/arknights/15-19`, which transcribes the in-game 剧情演出文本):

> 数据调用完成，行动人员已锁定。PRTS系统正在加载全局最优清除方案——
> PRTS检测到管理员权限......拒绝开放完整控制权限。警告：权限已失效。
> 识别到用户正在检索数据库，关键词：普瑞赛斯......访问权限已开放——
> {{color|ff2d00|你在找我，{@nickname}？可我现在不就在你面前吗？}}
> 你已经慢慢习惯你我之间的这个小游戏了。
> 你并不想就此认输，对吧？
> 你希望和过往的指挥一样收获一场胜利——
> 你笃信在Abyss更深处，一定能找到更多关于我的秘密——
> 我会满足你的心愿，Dr.{@nickname}。
> 管理员权限已确认：普瑞赛斯。 已禁用操作者所有权限。 警告：PRTS最终清除协议已启动......

Special clear-screen UI text:
> 你终于找**到我了**。
> 可你已经忘记了你我的约定。
> 离开。离开吧。
> 我们会在另一个地方相遇。

Final settlement-screen caption:
> 你总是不愿意放弃......是啊，这就是你。我很高兴你能回来。

---

### A4. SideStory「孤星」CW-9 / CW-ST-3

Source: `zh_CN/gamedata/story/activities/act25side/level_act25side_09_beg.json` and `..._09_end.json`
(`storyCode: "CW-9"`, `storyName: "恩怨纠葛"`, `eventName: "孤星"`)

`CW-9 行动前`: **zero** Priestess-tagged lines.
`CW-9 行动后` — she appears as 「思维共振」 (cognitive resonance) inside the Preserver's debate:

> 嗯。
> 只是她的思维共振。本来，这项技术应当是用于检查石棺中的休眠者的生命体征的，或是保存他们的尊严。
> 就像……进入你的梦，塑造你的梦。对你而言，我就是那个梦。
> 最接近的解释。但本质仍然有区别。
> 正如哲学家与辩论者们在古老的宫殿里所做的，当思想碰撞，言语交锋，他们的思绪会混为一体，不分你我。
> **你现在以“博士”的视角，在与“我”对话。但实际上，扮演“博士”的人是我，而你才是“我”。**

`CW-ST-3 「留下的人」`: **zero** Priestess-tagged lines (the Preserver talks *about* her there: the
"restraints on Kal'tsit's consciousness" beat). This matches the English wiki, which cites CW-ST-3
for Friston's dialogue about her, not for her own lines.

---

### A5. SideStory「众生行记」MT-9 / MT-ST-4

Source: `zh_CN/gamedata/story/activities/act42side/level_act42side_09_beg.json` and `..._09_end.json`
(`storyCode: "MT-9"`, `storyName: "解经"`, `eventName: "众生行记"`).
`MT-9 行动后` has **zero** Priestess lines.

> 这里很安静，我们不会再听见那些吵闹的动静了。
> 我不喜欢这样的景色，{@nickname}，太安静了些。
> 但我们别无他法，不是吗？
> 放松，你们在这里很安全。
> 我不会让那些萨科塔引发的混乱波及你们。
> 这和我当下所在意的事情相比，并不重要。
> 灾异？我只看到物种在演变，生灵在无谓地奔忙。
> 此刻拉特兰城中所发生的一切，都是PCS自行推演后输出的结果。
> 我只是在此之前对它重新做了校准，让它能回归原本的用途，以此来适配源石项目的进程。
> {@nickname}，我们的进度已经比预期落后了太多太多。
> 至少你并未遗忘自己求知的本性。
> PCS作为基于仿生学诞生的实验性质产物，曾为我们的科学团队和军队提供了不少便利。
> 但遗落在泰拉之后，由于长期缺乏维护，它的认知辐射增强器进入了半待机模式，运行效率已经极大衰减。
> 不过有趣的是，与泰拉本地物种接触之后，它反倒产生了出乎我意料的影响——
> 不仅受益者的认知与情绪得以共享，连物种特征都趋于同化。这一结果在我们过往的测试中从未出现。
> 令人惊喜，不是吗，{@nickname}？
> 别着急，{@nickname}，我会向你解释的。
> 不过，你的新同伴似乎有话想对你说。
> 敏锐的直觉，但缺乏了基础的认知。
> 这只是借助PCS系统向你们展示的某种可能性的幻影。
> **不再有时间，不再有色彩，一个永恒静滞之所。**
> {@nickname}，暂且在这难得的时间里与我同行吧，远离那些本就与你无关的纷争。
> 从你的语气中，我感受到了……恨。我理解。
> ——因为AMa-10，你的“凯尔希”。
> 当时你离开得太匆忙，你有许多疑惑尚未得到解答，而我也有很多猜测需要向你求证。
> 收好你的爪子。
> **“Mon3tr”，我尊重你给自己挑选的名字，但我比你自己更加了解你的本质。**
> {@nickname}，如果你想AMa-10回来，我可以帮你。你知道在哪里能找到我。
> 我知道这也是你所愿，“Mon3tr”。
> 你一直很执着于物质与现实的联系。
> 源石本就是我们创造的语言，我自然可以借助源石让我选定的目标听到我的声音。
> 对你们如此，对那台机器同样如此——

**MT-ST-4 「远行」** (source: `activities/act42side/level_act42side_st04.json`) — long block; the
`（未知语言）` tail is Priestess auditing the PCS/天使原型体, and contains the 「向源石许愿」 offer:

> ……
> {@nickname}，那些不起眼的字符，最终使得整个程序瘫痪……我们没法保证一套语言能够永远完美地运行下去。
> 我知道你想说什么，即使是源石，这套由我们创造的语言也依旧存在局限。
> 它需要更多的时间去调整，去自我迭代。
> 甚至有时我会忍不住胡思乱想，真正限制源石向完美形态演化的因素，或许并非其自身的设计瑕疵……而是我们自己。
> 人类的感性，抑或理性，都有可能为语言的发展套上枷锁。
> 创造源石的那段岁月里，我们也曾数次辩论过这一主张，但从无定论。
> 好在我们都接受这一不确定性存在于源石之中。
> ……记忆损伤可能也影响到了你发散思考的能力？
> 不过能看到你困惑的样子，我很开心。这与过往我和{@nickname}的交流模式截然不同。
> 完美，意味着确定的上限。但缺陷，却意味着我们仍有突破的可能性。这是{@nickname}的主张。
> 当我们必须解决的危机尚且无法言明时，所谓的完美只是自掘坟墓。
> ……
> 什么时候意识到的？
> 这并不难看出来，{@nickname}。
> 可直到此刻，你才敢鼓起勇气与我并肩而立。
> 我更希望此刻站在我身边的人，能平和地与我分享漫长休眠中，深深扎根于我们思维深处的孤独。
> ……可惜，你做不到。
> 我们的状态都不比以往。发生了太多事情，不是吗？
> 对我有了更多好奇？
> 现在的“Mon3tr”不再有任何的限制，她可以向你解答一部分的困惑。
> 你在害怕{@nickname}了解真相吗，AMa-10？
> 不过我更希望{@nickname}亲自来找我，就像刚才一样。
> 在石棺中的日子很难熬。思维如同悬浮在稠腻的泥沼中，我被动失去了对时间流淌的感知。
> 少有的慰藉是不断重复烙印在我们思维中的辩论，但并不是为了坚定我们共同立下的愿景……
> 我从不质疑我的道路。
> “辩论”，这是仅有的还能再与那个人交流的机会——
> 我并不奢求你现在就能理解我所思考的事情。在最后的日子到来之前，你都可以继续你所坚信的道路。
> 我们间的分歧注定延续，哪怕你都不再记得当初那人反对我的理由是什么。
> 我很期待你所爱的泰拉还能如何向我证明，你们的挣扎仍有价值……就像方才拉特兰的人们一样。
> ……
> **但是，我同样确定，预言家会归来。**
> **所以，{@nickname}，我会等着你。**
> 有时，我会觉得他们太像我们。如果你的时间还足够，说不定——
> ……
> **对了，我的确可以修好AMa-10。**
> **如果你下定了决心，向源石许愿吧，{@nickname}。**
> **我会听到你的声音。**

Then the `（未知语言）` audit block (still Priestess):

> （未知语言）我核验过你的底层代码，除去我重新调整维护的部分以外，在短时间内你自行更新迭代了更多。
> （未知语言）这仍不足以使你修复自身的逻辑漏洞？
> （未知语言）我本来还对你自我迭代的结果有极大的兴趣。
> （未知语言）现在看来，你错误地将自己视作了那个漏洞、那个悖论。
> （未知语言）这是超频运行的副作用？还是在缺少维护的环境里，长期与萨科塔进行数据交换污染了数据库？
> （未知语言）如果有更多的数据，或许我可以找到答案。
> （未知语言）可惜——我现在能调用的资源，已经不足以将你完全重启。
> （未知语言）否则，指挥系统因其对象的意愿而自我否定——这一现象足以重新唤起任何研究者对PCS系统的兴趣。
> （未知语言）……假如我们还在那个天才们用思想与主张针锋相对的时代的话。
> （未知语言）看来还是需要采取其他手段来继续推进项目进程——
> ……
> （未知语言）……重启？
> （未知语言）不对，没有任何回应我的迹象，也不符合PCS系统运作的逻辑。
> （未知语言）“天使”的“原型体”？
> （未知语言）但这套系统只是模仿“天使”的特性而设计，在建造时甚至并未植入任何“天使原型体”的样本。
> （未知语言）新诞生的“天使”？！怎么会……
> ……
> （未知语言）源石记录下了你的信息。
> （未知语言）在那束光来临之前，结局尚未确定。源石会成为我们的希望。
> （未知语言）“泰拉”。
> （未知语言）同胞，我们并不孤独。

---

### A6. 第八章 / 故事集「如我所见」 — no verbatim lines obtained

- **M8-8 行动后** (第八章「怒号光明」): the wiki states the Doctor has a flashback to Priestess
  placing them in the Sarcophagus. We did **not** extract this script (Ep8 keys exist in the index as
  `obt/main/level_main_08-*`). *Status: NOT VERIFIED for verbatim CN text.*
- **故事集「如我所见」/ Pignus**: PRTS refuses to tell the Doctor who Priestess is; a video of the
  Doctor and Priestess exists. English wiki cites `[[Pignus]]`. *Status: NOT VERIFIED for verbatim CN text.*

### A7. 第十六章「反常光谱」/ 第十七章「相变临界」 — newly added, beyond the brief

Sources: `obt/main/level_main_16-12_beg.json` (16-12 深埋地底, `eventName: 反常光谱`),
`obt/main/level_main_17-16_end.json` (`storyCode: 17-17` 不曾怀疑 行动后),
`obt/main/level_main_17-17_beg.json` (`storyCode: 17-18` 灵魂悄然 行动前, `eventName: 相变临界`),
`obt/main/level_st_17-04.json` (`storyCode: 17-21` 在暗夜中燃烧).

16-12 行动前: no Priestess-tagged lines. 17-17 行动后:
> 我也想修好它，和你一样。
> AMa-10不仅承载了我们共同的期待，它还保存了一段对我而言极为关键的记录。

17-18 行动前 (the AMa-10 origin scene):
> AMa-10的环境适应性测试成果很不错，也许很快我们就可以带这个小家伙去地面上走一走了。
> {@nickname}……啊，原来你在挑选要导入储存模块中的诗集？
> 虽然这原本不在AMa-10的预期功能之内，但我也很喜欢这样浪漫的小设计。
> 我知道，你从来不掩饰自己在一众研究项目中对AMa-10的偏爱，因为它最接近生命的形态，对吗？
> 你对AMa-10，还有遥远的未来，都怀有期许。这样的期许又何尝不是一份沉重的馈赠呢？
> 我们已经找到了自己的答案，希望这个小家伙足够聪明，可以理解这一份使命。
> 我也很期待，在那个遥远的将来，它又会以怎样的方式对下一个文明传颂我们的诗篇呢？
> AMa-10，能够理解这些诗歌吗？

17-21 在暗夜中燃烧:
> 可怜的孩子……我又该如何告诉你呢？
> 所有精神上的痛苦，都来源于对现实错误的认知。
> 可这是个体生命与这个宇宙之间永恒的鸿沟，也是文明必经的歧路，没有人可以超脱其外。
> 不过，不会太久了。
> **我会为你们带来答案。**

---

### A8. 语音记录 / voice lines — NOT VERIFIED

**We found NO 语音记录 (voice-line archive) entries for 普瑞赛斯.** She is an NPC, not a playable
operator, so she has no 干员语音 page. The only "voice"-adjacent item is 「她的角色EP《Eclipse》」
listed on 萌娘百科 (角色EP = character EP song, not voice lines). *Status: confirmed absent as
operator voice lines; EP existence from moegirl only.*

A related, verified item: **凯尔希·思衡托** (Kal'tsit's 异格/Alter form, 2026-05-01) DOES have a voice
line naming Priestess — 「晋升后交谈1」:
> 普瑞赛斯暂时不再威胁罗德岛的安全，她将选择交给了你。源石异变撕裂了这片大地隐藏起来的旧创，如果不加以引导，绝望很可能会先于灾难毁灭我们。无论何时，文明最大的敌人都是人类本身。
Source: `https://wiki.biligame.com/arknights/凯尔希·思衡托/默认/中文-普通话` (via biligame API).

---

## PART B — LORE MAP WITH EVENT ATTRIBUTION

Legend: **[CN-SCRIPT]** = line/scene read directly from the Chinese game script JSON.
**[CN-WIKI]** = Chinese wiki claim. **[EN-WIKI]** = English wiki.gg claim. **[SPEC]** = speculation.

### B1. Nature / identity — CONFIRMED

- She is a **"前文明"/旧文明 scientist**, race listed as **"Predecessor" (先史文明/前文明人类)**.
  [EN-WIKI infobox `race = "Predecessor"`; moegirl 「种族：**可能为**前文明人类」 — note moegirl hedges
  with 「可能为」, the EN wiki does not.]
- **Occupation: linguist (语言学家).** [CN-SCRIPT, 14-19 and 15-12 — she literally says
  「我叫普瑞赛斯，语言学家」 and 「我只是一个希望解释宇宙的语言学家」.]
- Status: **Alive**; her consciousness is preserved as information inside the **"最初的源石"**
  (moegirl) / **内化宇宙 Assimilated Universe** (EN-WIKI). [CN-WIKI + EN-WIKI; corroborated by
  [CN-SCRIPT] 15-12 「源石记录了你的信息」 and 「那同样只是一段无限重复的数据流而已」.]
- CN community nickname: **「牢普」**; moegirl 萌点 list includes 黑丝/科学家/黑长直/发箍/蝴蝶结/**病娇**/
  沉重. Illustrator: **唯@W (Wei@W)**. CV: 浅川悠 (JP, anime) / 许潇文 (CN, anime).
  [CN-WIKI. The CV tags are moegirl's category entries; treat as wiki-sourced.]

### B2. Relationship to 博士 / 预言家 (Oracle) — CONFIRMED

- The Doctor's **past name is 预言家 (Oracle)**. [CN-WIKI: 「普瑞赛斯与预言家相熟」;
  CN-SCRIPT 15-7/15-8 tag him as 预言家; CN-SCRIPT MT-ST-4 「我同样确定，预言家会归来」.]
- They met when the Doctor salvaged her **consciousness beacon (意识信标)** while she was anchored to
  a dying star, researching an oceanic planet's death-sounds. [CN-SCRIPT, 14-19 — full verbatim above.]
- They **travelled the universe together** via the ovoid ship (later *Rhodes Island*) and via
  consciousness projection. [CN-SCRIPT, 14-19.]
- She **rejects the word 「亲密」 (intimate)** as belittling. [CN-SCRIPT, 14-19 —
  「亲密？我不会用这种词语来形容我们之间的关系。」]
- 「牵手」 had "many different ways", often not requiring body parts. [CN-SCRIPT, 14-19.]
- She calls the Doctor the **true genius** behind Originium; the world called *her* the godlike
  creator. [CN-SCRIPT, 14-19 — 「真正的天才是你」.]
- They share **嵌于思维中的同样的灰质销钉 (the same Lynchpin embedded in their minds)**, which links
  their thoughts until their consciousnesses go extinct with the universe. [CN-SCRIPT, 15-17 变体01.]
- She **placed the Doctor in a 石棺 (Sarcophagus)** on Rhodes Island; colleagues left "before the
  stars fell"; she stayed alone with AMa-10. [CN-SCRIPT, 14-19 + EN-WIKI M8-8.]
- moegirl adds: she sensed the Doctor might wake early once, so she **tampered with the Doctor's
  灰质销钉**, then slept in another Sarcophagus. [CN-WIKI — this specific claim is moegirl's; the
  Lynchpin existence is [CN-SCRIPT]-confirmed, the tampering detail is wiki-level.]

### B3. 凯尔希 / Ama-10 / Mon3tr — CONFIRMED (high confidence)

- **She and the Doctor created AMa-10 (= 凯尔希 / Kal'tsit).** [CN-SCRIPT 15-17:
  「是你啊……AMa-10」+「我怎会不认识自己倾注了情感的造物呢？」; CN-WIKI: 「二人一同制造了Ama-10」;
  EN-WIKI: "the two created AMa-10 aka. Kal'tsit".]
- **The AMa-10 project's original purpose**, verbatim from 凯尔希·思衡托 档案资料三 [CN-WIKI, biligame]:
  > 博士现在不知道的是，AMa-10项目的初衷，是在寂静降临后，让代号为AMa-10的个体作为量产型多功能机器，协助幸存的人类重建家园。而为了满足这个设计目的，一个最基本的需求即是AMa-10不可被■■■识别为生命体。
  (i.e. AMa-10 was a **mass-production multi-function machine** to help surviving humans rebuild
  after the Silence; it **must not be recognized as a lifeform by ■■■**.)
- **Priestess placed restraints on Kal'tsit's consciousness** — confirmed via [CN-SCRIPT] 15-17:
  「你已经打破了我设下的语言的禁令，对吗？」 (a **language ban/禁令**, not a generic restraint).
  EN-WIKI frames this via CW-ST-3 as "restraints on Kal'tsit's consciousness". 凯尔希·思衡托
  档案资料四 [CN-WIKI] also confirms she received her mission from the one **then named 预言家**.
- **Kal'tsit severed her own 双生循环 (gemini cycle)** to break free of Priestess's control.
  [CN-SCRIPT, 15-17 行动后 — 「你以切断自己双生循环的系统为代价来脱离我的控制」.]
- 凯尔希·思衡托 档案资料五 [CN-WIKI] shows the 双生循环系统 simulation log ending
  「欢迎回来，凯尔希。」
- **Priestess crystallized and "killed" Kal'tsit in 15-17**, leaving only her coat; Mon3tr cocooned.
  [EN-WIKI citing 15-17; the fight dialogue is [CN-SCRIPT]-confirmed above.]
- **MT-ST-4: she offers to repair AMa-10 if the Doctor wishes to Originium.**
  [CN-SCRIPT — 「我的确可以修好AMa-10。如果你下定了决心，向源石许愿吧」.]
- 「思衡托原理」/「凯尔希·思衡托」: Kal'tsit's full name comes from an ancient **linguist's**
  unfinished universal language, in which the word means **"hope"**. [CN-WIKI, biligame
  凯尔希·思衡托 档案资料四]. **The text does NOT name Priestess as that linguist** — it says
  「某位语言学家」. [SPEC: community reads this as Priestess, since she is *the* linguist. Mark as
  **unconfirmed inference**.]

### B4. PRTS — CONFIRMED verbatim (this resolves a major fan question)

- **Priestess developed/designed PRTS; the Doctor (预言家) improved it.**
  [CN-SCRIPT, 15-7 行动后 — 预言家: 「（未知语言）**改进你设计出来的PRTS花了点时间**。」 This is the
  strongest single confirmation. moegirl independently says the same and calls it "基本可以证实".]
- Priestess **has admin/administrator authority over PRTS**; her Sarcophagus powered PRTS and stored
  its code. [CN-WIKI; corroborated by [CN-SCRIPT]-adjacent 15-19 narration: 「管理员权限已确认：普瑞赛斯。
  已禁用操作者所有权限。」]
- She **tampered with PRTS** to operate outside Rhodes Island's control (15-4 行动后), and controlled
  Originium to grow crystals through the landship (15-11 行动后). [EN-WIKI citing those scenes.]
- 「EYES OF PRIESTESS」 appears on the operation map recordings — the letters spell **PRTS**.
  [CN-WIKI] — this is an **in-game visual easter egg**, and the same wiki explicitly labels the
  "Priestess IS PRTS" conclusion as **unconfirmed by the developers**. [SPEC — do not assert.]
- 众生行记 update replaced PRTS with 可露希尔's **ZOOT零号油罐** in places. [CN-WIKI.]

### B5. 源石 (Originium) / 内化宇宙 (Assimilated Universe) — CONFIRMED

- **She co-created Originium with the Doctor (预言家).** [CN-SCRIPT 14-19:
  「我们争论与碰撞的结晶」/「所有人都说，我是那个创造了源石与未来…的人。但我一直都知道，真正的天才是你」;
  CN-WIKI; EN-WIKI.]
- **Originium is a *language*** she created with the Doctor to decipher the ultimate question and face
  **"It" (祂) / the Observer**. [CN-SCRIPT MT-ST-4: 「源石本就是我们创造的语言」; CN-SCRIPT 15-16/
  15-18: 「我们研发的技术」. EN-WIKI states this explicitly for 15-16.]
- **内化宇宙 (Assimilated Universe)**: Originium stores assimilated matter **as information**;
  inside Originium "there exists a universe". [CN-WIKI: 「将其同化的物质以信息的形式存放于源石的
  『内化宇宙』中」; CN-SCRIPT 14-19: 「这里嘛……『不可知』」 + tomb world description.]
- **Division of intent** — the core conflict: **预言家 wanted Originium to aid/beacon future
  civilizations; 普瑞赛斯 wanted it to assimilate all of Terra so civilization survives as
  information.** [CN-WIKI, explicit; consistent with CN-SCRIPT MT-ST-4 「完美…缺陷」 debate and
  15-18 「源石同化这颗星球的速度并未达到我的预期」.]
- Originium is the cause of **Terran evolution** (normal beasts came to resemble the Predecessors).
  [EN-WIKI citing 15-16. Not re-verified in CN script text by us.] *Status: EN-WIKI only.*
- The 菱形 (rhombus) is the **"symbol of Originium"**, ubiquitous in the Assimilated Universe.
  [EN-WIKI citing 14-21.]
- She considers the Terran civilization a **"mistake" born of probability**. [CN-SCRIPT 15-12:
  「是的，这是一个错误，你们的存在是计划之外的状况。」]

### B6. 特蕾西娅 (Theresa) / 特雷西斯 (Theresis) — CONFIRMED (mostly via EN-WIKI + CN-WIKI)

- The Doctor's amnesia results from **特蕾西娅's influence**, which is why Priestess's memory-restoration
  attempt in 14-19 fails. [CN-WIKI: 「发现博士已经在特蕾西娅的影响下失忆」; EN-WIKI 14-19.]
- **特蕾西娅 left a backdoor restricting Priestess's access to 阿喃那 (Amnannam)**. [EN-WIKI 14-22;
  CN-WIKI 「特蕾西娅的计划完成后，普瑞赛斯抹除了特蕾西娅制造的高塔」.]
- **特雷西斯 entered the 内化宇宙** to seize Amnannam's control. Priestess extracted his memories of
  **阿斯卡纶 (Ascalon)** and weaponized them against him; he broke through, **traded being heavily
  assimilated by Originium (dying) to seize part of Amnannam's authority**, forcing her into **3 years
  of dormancy**. [CN-WIKI, detailed. EN-WIKI frames it as Theresis "passing judgement upon the gods".]
  *Status: CN-WIKI-level; we did not extract the 14-22 script text for these beats.*
- Theresis's attack cracks the white wall; the golden sea floods in; her connection weakens; she pulls
  the dying Infected Cautus **希尔达 (Hierda)** into her realm. [EN-WIKI citing 15-16.]
- CN community frames Priestess vs Theresa as the "two wives/争抢博士" meme axis. [CN-WIKI, 梗与二创
  section — this is **fandom**, explicitly labeled as such by the wiki.] [SPEC]

### B7. 星荚/屏障 (Starpod), 巴别塔 (Babel), 石棺 (Sarcophagus), 灰质销钉 (Lynchpin) — MIXED

- **石棺 (Sarcophagus)** — CONFIRMED as a major plot device: the Doctor sleeps in one; Priestess's
  Sarcophagus powers PRTS and stores its code; it is located in the **Abyss** region of Rhodes Island;
  Kal'tsit·思衡托 档案资料二 calls the Sarcophagus 「家用生理修复仪」 and discusses its theory.
  [CN-WIKI + CN-SCRIPT 15-17 + biligame 凯尔希·思衡托.]
- **灰质销钉 (Lynchpin)** — CONFIRMED verbatim (see A3 变体01: 「嵌于我们思维中的同样的灰质销钉」).
  Note: we found **no** in-script definition of 灰质销钉 beyond it being a shared mind-link device.
- **巴别塔 (Babel)** — she appears in the **Babel** SideStory (BB-ST-2 confirmed CN-SCRIPT). Babel as
  an organization is 特蕾西娅's ideal, later co-run by Kal'tsit (act33side 01/05) [CN-WIKI].
- **星荚/屏障 (Starpod)** — we did **NOT** find any 普瑞赛斯-attributed 星荚 line. *Status: NOT VERIFIED.*
  (Related but distinct: Kal'tsit·思衡托 档案资料四 mentions 阻隔层 — 「人们能够突破阻隔层的桎梏」 —
  which is likely the same concept, but this is Kal'tsit speaking about her wish, not Priestess.)

### B8. 天堂支点 / 伐木工 / 观察者 — PARTIALLY CONFIRMED

- **伐木工 (Lumberer)** — the *concept* is CONFIRMED verbatim, but the **Chinese game text does NOT
  use the noun 「伐木工」**. The actual line [CN-SCRIPT, 15-12, speaker 温柔的声音 = Priestess] is:
  > **一个绝对存在的终极孜孜不倦地收割着这可怜树桩上新发出的枝桠，而我们却对祂一无所知。**
  and it is attributed to "someone very important to me" (i.e. the Doctor/预言家) who first described
  the tombstone as a snapped tree trunk. 「伐木工」 is therefore a **fan/wiki coinage**, not in-game
  text. **Mark this clearly in the report.**
- **观察者 (Observer)** — the entity is real (EN-WIKI calls it "It"/"the inevitable end"; CN-SCRIPT
  consistently uses **「祂」** and 「一个绝对存在的终极」). We did **NOT** find the Chinese proper noun
  「观察者」 in any script we extracted. *Status: the entity is CONFIRMED; the CN term 「观察者」 is NOT
  verified by us.*
- **天堂支点** — CN-WIKI states she activated 「天堂支点」 using AMa-10's authority in **第十七章
  「相变临界」**, hoping Terra can prove its worth against 「伐木工」. We searched our downloaded Ep17
  scripts (17-1, 17-17, 17-18, 17-19, 17-20, 17-21, EG-11) and found **no** occurrence of 「天堂支点」 or
  「伐木工」. *Status: CN-WIKI claim only; NOT independently verified in script text.* **Flag as
  unverified.**
- The **「那束光」 (that ray of light)** sequence in 15-12 is CONFIRMED verbatim and is the clearest
  in-game depiction of the Observer/祂 destroying a civilization.

### B9. 终末地 (Endfield) connections — NOT VERIFIED

We found **no** verified in-game or wiki-source link between 普瑞赛斯 and 明日方舟：终末地 in the
sources we accessed. The 终末地 official site appeared in search results but contained nothing about
her. *Status: NOT VERIFIED — do not assert any Endfield connection.*

### B10. Appearance list (which events/chapters she appears in) — CONFIRMED

From EN-WIKI infobox (Major appearances) + CN-WIKI 角色经历 + our own script verification:

| # | Appearance | Our verification status |
|---|---|---|
| 1 | **SideStory「巴别塔」** (BB-ST-2) | ✅ Script extract**ED**, verbatim CN obtained |
| 2 | **第八章「怒号光明」** (M8-8, flashback) | ⚠️ wiki-attested; script not extracted |
| 3 | **故事集「如我所见」** (Vigilo / Pignus, flashback) | ⚠️ wiki-attested; script not extracted |
| 4 | **第十四章「慈悲灯塔」** (14-19, 14-21, 14-22) | ✅ 14-19 extracted verbatim; 14-22 mentions her by name |
| 5 | **SideStory「孤星」** (CW-9 行动后; CW-ST-3 discusses her) | ✅ Script extracted, verbatim CN obtained |
| 6 | **第十五章「离解复合」** (15-3, 15-4, 15-9, 15-11, 15-12, 15-15, 15-16, 15-17, 15-18, 15-19, 15-21) | ✅ Scripts extracted for 15-7, 15-8, 15-12, 15-17(×3), 15-18 |
| 7 | **SideStory「众生行记」** (MT-9, MT-10, MT-ST-4) | ✅ MT-9 + MT-ST-4 extracted verbatim |
| 8 | **第十六章「反常光谱」** | ✅ 16-12 fetched; no Priestess-tagged lines found |
| 9 | **第十七章「相变临界」** | ✅ 17-17, 17-18, 17-21 extracted verbatim |
| 10 | **Arknights Concept Trailer 4** | ⚠️ EN-WIKI only |

CN-WIKI additionally notes her in-game **UI corruption event**: after clearing **15-21**, the game
**irreversibly** switches to a Priestess-corrupted visual state (map glitching, forced Rhodes Island
logo on loading screens, tips replaced by her messages, the PRTS logo swapped for the Originium
rhombus, the "接管代理作战" button turned to mojibake). [CN-WIKI]. This is a notable, verifiable
game-state fact.

---

## PART C — CONFIRMED vs SPECULATION (explicit split)

### CONFIRMED — read directly from Chinese game script JSON (highest confidence)
1. Her self-introduction: 「我叫普瑞赛斯，语言学家。我正在研究行星死去时发出的最后声波。我喜欢安静地独处，但也想和合适的人一起探索宇宙。」 (14-19)
2. 预言家 improved the PRTS **she** designed. (15-7 行动后)
3. She and 预言家 created AMa-10 / 凯尔希. (15-17 + 17-18)
4. 灰质销钉 links their minds. (15-17 变体01)
5. Originium is a **language** they created together; "true genius" was the Doctor. (14-19, MT-ST-4)
6. 「群星正在褪色…这里很快也会安静下来」 (BB-ST-2)
7. 「是你啊……AMa-10。同样好久不见了。」 (15-17 行动前)
8. Closing 14-19 caption 「我的身边将是你的归处」 (the "return to me" beat)
9. The Observer/祂 as 「一个绝对存在的终极孜孜不倦地收割着这可怜树桩上新发出的枝桠」 (15-12)
10. She offers to repair AMa-10 in exchange for a wish to Originium. (MT-ST-4)
11. 15-19 PRTS takeover lines 「你在找我，{@nickname}？」, 「我会满足你的心愿，Dr.{@nickname}。」 (biligame transcription)
12. 「源石同化这颗星球的速度并未达到我的预期」 — the assimilation-rate disappointment. (15-18)
13. Terran civilization as 「一个错误…计划之外的状况」. (15-12)

### WIKI-SOURCED (credible but we did not read the script ourselves)
- Her race field = "Predecessor"; status Alive; 「最初的源石」 as her storage medium.
- The 3-year dormancy after 特雷西斯's raid; the memory-extraction attack using 阿斯卡纶's memories.
- PRTS admin authority / Sarcophagus powering PRTS (partially script-adjacent via 15-19).
- 15-21 irreversibly corrupting the game UI.
- 「天堂支点」 activated in 第十七章.
- KAma-10 project purpose (from the 凯尔希·思衡托 operator archive — this is official in-game
  operator text, so treat as high confidence, but it is operator 档案 not main-story script).

### SPECULATION / FANDOM — do NOT present as fact
- **「普瑞赛斯 = PRTS」 as an identity.** The wiki itself says 「上述猜想目前没有得到官方的证实」.
  The PRTS *authorship* link is confirmed; the *identity/avatar* link is not.
- **「伐木工」 as an in-game proper noun.** Not in the CN script; the game says 「一个绝对存在的终极」.
- **「观察者」 as an in-game proper noun.** Entity confirmed; the CN label is not verified by us.
- **Priestess as the 「某位语言学家」 behind 思衡托原理.** Plausible but the text does not name her.
- **Priestess as the Doctor's 「正宫」/「病娇女鬼」, Theresa as 「小三」 etc.** Pure fandom meme
  (moegirl's 梗与二创 section). Must be labeled as community culture, not lore.
- 「凯尔希 = 博士和普瑞赛斯养的猫」 — fandom joke.
- **Any 终末地 connection.** Not verified, no source found.

---

## PART D — EXPLICIT LIST OF WHAT WE COULD NOT VERIFY

1. **语音记录 / voice lines for 普瑞赛斯.** She has none — she is an NPC and has no operator voice
   archive. The only related artifact is her character EP 「《Eclipse》」 (moegirl-listed).
2. **M8-8 行动后 (第八章) verbatim CN text** — the Sarcophagus flashback. Not extracted.
3. **故事集「如我所见」/ Pignus verbatim CN text** — the PRTS refusal + video scene. Not extracted.
4. **14-21 and 14-22 verbatim CN text** — the rhombus/"symbol of Originium" and the Theresa backdoor.
   We only confirmed that 14-22's text contains the string 「源石。真相。普瑞赛斯。特蕾西娅。」.
5. **「天堂支点」 and 「伐木工」 as in-game terms.** Searched all downloaded Ep15/16/17 scripts; zero
   hits for either string.
6. **「观察者」 as a Chinese proper noun.** Zero hits in downloaded scripts.
7. **星荚/屏障 (Starpod) in connection with Priestess.** Zero verified hits.
8. **终末地 (Endfield) connections.** Nothing found.
9. **15-16 行动前/行动后 verbatim text** — the 14-22-adjacent Theresis confrontation. (We did fetch
   the file whose `storyCode` is 15-18, which is the 15-18 stage; the stage *numbered* 15-16 maps to a
   different JSON key we did not isolate.)
10. **Exact scene citation for 「Long time no see」 as EN-WIKI renders it.** The CN text is
    「同样好久不见了」 and is addressed to AMa-10 in 15-17, not a bare 「好久不见」 to the Doctor.
11. **Her JP/EN localized lines.** We worked from `zh_CN` only. No `ja_JP`/`en_US` cross-check was done.
12. **Whether 「前文明」 vs 「先史文明」 is the correct CN term.** Both appear across sources; the
    script itself uses 「未知语言」-era framing rather than these labels. moegirl uses 「前文明」.
13. **Arknights Concept Trailer 4** appearance — EN-WIKI only, not independently checked.

---

## PART E — REPRODUCIBILITY (exact commands used)

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 1) Chinese story index (420 KB, ~all CN story keys)
curl -sL -A "$UA" "https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/storyinfo.json" -o si_cn.json

# 2) One script (14-19 行动前) — the self-introduction
curl -sL -A "$UA" \
 "https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/gamedata/story/obt/main/level_main_14-17_beg.json" \
 -o 14-19_beg.json

# 3) Extract Priestess lines from any script
grep -o '"prop": "name", "attributes": {"content": "[^"]*", "name": "普瑞赛斯"' FILE.json \
 | sed -e 's/.*"content": "//' -e 's/", "name": "普瑞赛斯"//'

# 4) Cross-check a claim exists anywhere in the corpus
grep -ho '"content": "[^"]*天堂支点[^"]*"' *.json

# 5) English wiki.gg lore page (API parse still works even when the site HTML is rate-limited)
curl -s -A "$UA" "https://arknights.wiki.gg/api.php?action=parse&page=Priestess&prop=wikitext&format=json&formatversion=2"

# 6) Chinese lore summary
curl -s -A "$UA" -H "Accept-Language: zh-CN,zh;q=0.9" \
  "https://mzh.moegirl.org.cn/%E6%99%AE%E7%91%9E%E8%B5%9B%E6%96%AF" -o mg.html   # then strip tags

# 7) biligame MediaWiki API (works; useful for operator archives & some stage narration)
curl -s -A "$UA" --get --data-urlencode "action=parse" --data-urlencode "page=凯尔希·思衡托" \
  --data-urlencode "prop=wikitext" --data-urlencode "format=json" --data-urlencode "formatversion=2" \
  "https://wiki.biligame.com/arknights/api.php"
```

Note on tooling: `python3` and `node` are broken in this shell per the brief; we used only
`curl` + `grep` + `sed` + `awk`. This was sufficient.

---

## PART F — SOURCE URL LEDGER (every claim's source)

| Claim / data | Source URL |
|---|---|
| All CN script quotes (14-19, 15-7, 15-8, 15-12, 15-17, 15-18, 16-12, 17-17, 17-18, 17-21, BB-ST-2, CW-9, MT-9, MT-ST-4) | `https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/gamedata/story/<key>.json` |
| CN story index / key list | `https://cdn.jsdelivr.net/gh/050644zf/ArknightsStoryJson@main/zh_CN/storyinfo.json` |
| Data-mirror discovery | `https://astr.pages.dev/assets/main.f6fc65f5.js` and `https://astr.pages.dev/` |
| English lore overview + per-scene citations | `https://arknights.wiki.gg/api.php?action=parse&page=Priestess&prop=wikitext&format=json&formatversion=2` |
| English 14-19 full script | `https://arknights.wiki.gg/api.php?action=parse&page=14-19/Story&prop=wikitext&format=json&formatversion=2` |
| EN BB-ST-2, 15-17 | `.../api.php?action=parse&page=BB-ST-2...`, `.../page=15-17/Story...` |
| CN lore summary, appearance list, fandom section | `https://mzh.moegirl.org.cn/普瑞赛斯` (rev 8469841) |
| 15-19 PRTS takeover narration (CN) | `https://wiki.biligame.com/arknights/15-19` |
| AMa-10 project purpose, 思衡托原理, 双生循环 log, Priestess-naming voice line | `https://wiki.biligame.com/arknights/凯尔希·思衡托` (+ `/默认/中文-普通话`) |
| 离解复合 variant-file mapping (白/蓝问卷) | `https://wiki.biligame.com/arknights/离解复合` |
| Search entry point (biligame) | `https://wiki.biligame.com/arknights/api.php?action=query&list=search&srsearch=普瑞赛斯` |

Local artifacts from this research session (in the workspace `priestess_research/` dir):
`mg2.txt` (moegirl plain text), `kaltsit.txt` (biligame 凯尔希·思衡托 wikitext), and in `/tmp/scr/`
the downloaded script JSONs plus extracted per-scene line dumps (`d1417beg.txt`, etc.).

---

*End of findings. Nothing above is invented; every quoted Chinese line was read out of a fetched
file, and every wiki-level claim is attributed.*
