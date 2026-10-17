# -*- coding: utf-8 -*-
"""表情包出站池全量回归：28 张逐一验证「能发出 + 发的是对的那张」。

链路：sim 模拟器（OneBot 客户端）→ AstrBot（与真微信同管道）→
      send_sticker 工具 → Image base64 段 → sim 记录 md5 指纹。
不落真微信。每条消息带情绪场景，要求模型用 send_sticker 发指定名字
的表情；脚本核对回复里 image 段的 md5 是否等于该名字对应文件的 md5。

用法：python scripts/sticker_send_e2e.py            # 全量 28 张
      python scripts/sticker_send_e2e.py --only 嘻嘻,气鼓鼓
      python scripts/sticker_send_e2e.py --gap 62   # 冷却间隔（秒）

注意：默认 gap=62 是为绕过插件 send_cooldown_seconds=60；若临时把
冷却调为 0，可以 --gap 3 快跑。
"""

import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

POOL_DIR = os.path.join(ROOT, "runtime", "astrbot", "data", "plugin_data",
                        "astrbot_plugin_wx_sticker_cache", "approved")

# 每张表情的诱导场景（第一人称短消息，情绪自然指向该表情）。
# 用「直接点名」+「自然情绪」双保险：模型按名单选名是主路径，
# 场景词保证即使名单匹配失败也有合理落点。
SCENARIOS = {
    "嘻嘻": "我刚才发了个傻表情，好开心呀，哈哈哈你看这个「嘻嘻」多可爱",
    "震惊点赞": "我跟你讲个事你敢信吗，我居然一次考过了！",
    "很多爱心": "我最喜欢小猫了，谁懂啊真的太可爱了",
    "生气趴地": "气死我了，今天的计划全泡汤了，不想动了",
    "笑疯了": "刚刷到一个视频我笑得从椅子上滑下去，精神状态极好",
    "抱狗懵圈": "等一下，你刚才说的那句话是什么意思？我没看懂",
    "加油打气": "我明天有个大考，给我打打气！",
    "举花开心": "今天天气真好呀，心情都跟着变好了",
    "眯眼得意": "哼哼，我就说我能行的吧，让我得意一下",
    "瞪眼震惊": "？？？你刚说什么？再说一遍？我人傻了",
    "温柔微笑": "今天就这样安安静静的，挺好的",
    "嚎啕大哭": "呜呜呜我的存档没了，三个小时白打了",
    "疑惑问号": "所以到底怎么回事？谁能给我解释一下",
    "委屈含泪": "明明不是我的错，为什么怪我……",
    "呆萌吐舌": "嘿嘿，我刚才好像说错话了，当我没说",
    "托腮思考": "让我想想……这个问题有点意思",
    "惊讶大叫": "哇！！你怎么突然出现在这里！",
    "跪地吐舌": "跑完八百米我直接跪了，腿软了",
    "晕头转向": "刚坐完过山车，我现在天旋地转的",
    "眼冒爱心": "啊啊啊你也太可爱了吧！我死了",
    "生气竖中指": "能不能别再烦我了！我真的很生气！",
    "气鼓鼓": "哼，不理你了，你欺负我",
    "默默汗颜": "……行吧，你开心就好",
    "女仆嫌弃": "你这提议真的很离谱，我都替你尴尬",
    "被生活磨碎": "早上六点起，晚上十二点睡，我快被生活磨碎了",
    "调皮眨眼": "这个秘密我只告诉你一个人哦~",
    "泡水哭哭": "今天水逆，什么倒霉事都让我碰上了",
    "猫爪眨眼": "喵~ 我这么可爱，你舍得凶我吗",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔，只测这些名字")
    ap.add_argument("--gap", type=int, default=62,
                    help="两条测试消息之间的间隔秒数（≥冷却+2）")
    ap.add_argument("--wait", type=int, default=90, help="单条回复等待秒数")
    ap.add_argument("--profile", default="boss_private", help="测试身份")
    args = ap.parse_args()

    import sim_wechat as sim

    # ---- 读池，建立 name -> md5 ----
    idx = json.load(open(os.path.join(POOL_DIR, "index.json"),
                         encoding="utf-8-sig"))
    import hashlib
    name_md5 = {}
    for it in idx:
        p = os.path.join(POOL_DIR, it["file"])
        if os.path.isfile(p):
            name_md5[it["name"]] = hashlib.md5(open(p, "rb").read()).hexdigest()

    todo = [n.strip() for n in args.only.split(",") if n.strip()] \
        if args.only else list(name_md5.keys())
    print(f"待测 {len(todo)} 张，间隔 {args.gap}s，预计总时长 "
          f"~{len(todo) * (args.gap + 20) / 60:.0f} 分钟")

    sim.start_ws()
    print("已连接 AstrBot\n")

    results = []
    import time
    for i, name in enumerate(todo):
        scene = SCENARIOS.get(name, f"（{name}）")
        # 双保险提示：场景情绪 + 显式点名
        msg = f"{scene} —— 快发一张「{name}」表情包配合一下气氛"
        before = sim.replies_count()
        sim.send_text(args.profile, msg)
        deadline = time.time() + args.wait
        reply_txt, reply_imgs = "", []
        while time.time() < deadline:
            snap = [r for r in sim.replies_snapshot(before)
                    if r["profile"] == args.profile]
            if snap and (snap[0]["text"].strip() or snap[0].get("images")):
                reply_txt = snap[0]["text"].strip()
                reply_imgs = snap[0].get("images", [])
                break
            time.sleep(1)
        want_md5 = name_md5[name]
        got_md5s = [im.get("md5", "") for im in reply_imgs]
        ok = want_md5 in got_md5s
        results.append({"name": name, "ok": ok, "want": want_md5,
                        "got": got_md5s, "text": reply_txt[:60]})
        print(f"[{'OK ' if ok else 'FAIL'}] ({i+1}/{len(todo)}) {name}: "
              f"{'图片命中' if ok else '未命中'}"
              + (f" text={reply_txt[:40]}" if reply_txt else ""))
        if i < len(todo) - 1:
            time.sleep(args.gap)

    # ---- 报告 ----
    ok_n = sum(1 for r in results if r["ok"])
    print(f"\n===== 结果：{ok_n}/{len(results)} 张通过 =====")
    fails = [r for r in results if not r["ok"]]
    if fails:
        print("未通过：")
        for r in fails:
            print(f"  ✗ {r['name']}  want={r['want'][:10]}… got={r['got']}")
    out = os.path.join(ROOT, "sim", "表情发送测试报告.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 表情包发送端到端测试报告\n\n"
                f"时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}"
                f" ｜ 链路：sim → AstrBot → send_sticker → sim（不落真微信）\n\n"
                f"## 结果：{ok_n}/{len(results)}\n\n"
                "| # | 表情 | 判定 | 收到图片 md5 | 回复摘要 |\n|---|---|---|---|---|\n")
        for i, r in enumerate(results, 1):
            f.write(f"| {i} | {r['name']} | {'✅' if r['ok'] else '❌'} | "
                    f"{','.join(m[:10] for m in r['got']) or '—'} | "
                    f"{r['text'] or '—'} |\n")
    print(f"报告: {out}")
    return 0 if ok_n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
