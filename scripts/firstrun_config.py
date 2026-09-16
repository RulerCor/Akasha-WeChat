# -*- coding: utf-8 -*-
"""firstrun_config.py — 便携版「首次配置」向导。

跑一次，把收件人自己的凭据写进配置：
  1. WeFlow Access Token —— 优先自动从 %APPDATA%\\WeFlow\\WeFlow-config.json 读
  2. 机器人微信昵称 / wxid
  3. 对话模型（API Key + 地址 + 模型名）

读不到就提示手填。全程不联网、不上传任何东西。

写完后在包根创建 `.first_run_done`，启动脚本据此判断是否已配置。
"""

import io
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASTRBOT_DATA = os.path.join(ROOT, "app", "astrbot", "data")
CMD_CONFIG = os.path.join(ASTRBOT_DATA, "cmd_config.json")
BRIDGE_CONFIG = os.path.join(ROOT, "app", "bridge", "config.json")
KBMARK = os.path.join(ROOT, ".first_run_done")

# 常见服务商预设：(显示名, 源类型, api_base, 常用模型建议)
PRESETS = [
    ("DeepSeek 深度求索", "openai_chat_completion",
     "https://api.deepseek.com/v1", "deepseek-chat"),
    ("月之暗面 Kimi", "openai_chat_completion",
     "https://api.moonshot.cn/v1", "kimi-k2-0905-preview"),
    ("硅基流动 SiliconFlow", "openai_chat_completion",
     "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
    ("阿里云百炼（通义）", "openai_chat_completion",
     "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("OpenRouter", "openrouter_chat_completion",
     "https://openrouter.ai/api/v1", "deepseek/deepseek-chat"),
    ("自定义（任意 OpenAI 兼容接口）", "openai_chat_completion", "", ""),
]


def line(ch="─", n=66):
    print(ch * n)


def ask(prompt, default="", required=True):
    while True:
        d = f"（默认 {default}）" if default else ""
        try:
            v = input(f"{prompt}{d}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(1)
        if not v and default:
            return default
        if v or not required:
            return v
        print("  ← 这一项不能留空，请重新输入。")


def load_json(p):
    try:
        return json.load(io.open(p, encoding="utf-8-sig"))
    except Exception:
        return None


def save_json(p, d):
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(d, ensure_ascii=False, indent=2))


def detect_weflow():
    """从 WeFlow 自己的配置里读 token / 自己的 wxid（读不到返回空）。"""
    cands = [
        os.path.join(os.environ.get("APPDATA", ""), "WeFlow", "WeFlow-config.json"),
        os.path.join(os.environ.get("APPDATA", ""), "weflow", "WeFlow-config.json"),
    ]
    for p in cands:
        d = load_json(p) if os.path.isfile(p) else None
        if isinstance(d, dict):
            return str(d.get("httpApiToken") or ""), str(d.get("myWxid") or ""), p
    return "", "", ""


def main():
    print()
    line("═")
    print("   Akasha 便携版 · 首次配置")
    line("═")
    print()
    print("  接下来要填三项：WeFlow Token、机器人昵称、对话模型。")
    print("  所有内容只写进本机配置文件，不会上传。")
    print("  建议先把微信登录好、并让 WeFlow 完成一次初始化，再来跑这个向导。")
    print()
    line()

    # ---------- 1. WeFlow ----------
    print("\n【1/3】WeFlow 接入")
    tok, mywxid, path = detect_weflow()
    if tok:
        print(f"  已从 WeFlow 配置里读到 Token（{path}）")
        print(f"  Token 前 6 位: {tok[:6]}…")
        if mywxid:
            print(f"  该账号 wxid: {mywxid}")
        ans = ask("  直接使用这个 Token？(y/n)", "y")
        if ans.lower().startswith("n"):
            tok = ""
    if not tok:
        print("  没读到 WeFlow 配置。请打开 WeFlow → 设置 → 打开 HTTP API，")
        print("  把里面显示的 Access Token 复制过来。")
        tok = ask("  WeFlow Access Token")

    # ---------- 2. 机器人身份 ----------
    print("\n【2/3】机器人身份")
    print("  昵称用于判断群里有没有人在叫它（@ 它）。多个用逗号分隔。")
    nick = ask("  机器人微信昵称（逗号分隔）", "Mon3tr")
    nicks = [x.strip() for x in nick.replace("，", ",").split(",") if x.strip()]
    print("  wxid 可留空（防自回复用，留空也能跑）。")
    if mywxid:
        print(f"  WeFlow 那边读到的是: {mywxid}")
    wxid = ask("  机器人自己的 wxid（可留空）", mywxid or "", required=False)

    # ---------- 3. 模型 ----------
    print("\n【3/3】对话模型（不配就无法回复）")
    for i, (nm, _, base, mdl) in enumerate(PRESETS, 1):
        print(f"  {i}. {nm}" + (f"   [{base}]" if base else ""))
    while True:
        c = ask("  选一个（填编号）", "1")
        try:
            idx = int(c) - 1
            if 0 <= idx < len(PRESETS):
                break
        except ValueError:
            pass
        print("  ← 请输入 1~%d 的编号。" % len(PRESETS))

    nm, stype, api_base, model_default = PRESETS[idx]
    if not api_base:
        api_base = ask("  接口地址（形如 https://xxx/v1）")
    else:
        api_base = ask("  接口地址", api_base)
    model = ask("  模型名", model_default or "")
    api_key = ask("  API Key")

    # ---------- 写入 ----------
    print("\n正在写入配置...")

    # 桥接
    bc = load_json(BRIDGE_CONFIG)
    if bc is None:
        print(f"  ❌ 读不到 {BRIDGE_CONFIG}")
        return 1
    bc["access_token"] = tok
    bc["bot_nicknames"] = nicks
    bc["bot_wxid"] = wxid
    save_json(BRIDGE_CONFIG, bc)
    print("  ✔ 桥接配置")

    # AstrBot
    d = load_json(CMD_CONFIG)
    if d is None:
        print(f"  ❌ 读不到 {CMD_CONFIG}")
        return 1

    srcs = d.setdefault("provider_sources", [])
    provs = d.setdefault("provider", [])

    # 全部停用，只留用户刚配的这一个
    for s in srcs:
        if isinstance(s, dict):
            s["enable"] = False
    for p in provs:
        if isinstance(p, dict):
            p["enable"] = False

    src_id = "user-configured"
    tpl_src = next((s for s in srcs
                    if isinstance(s, dict)
                    and s.get("type") == "openai_chat_completion"), None)
    tpl_prov = next((p for p in provs
                     if isinstance(p, dict) and p.get("modalities")), None)

    if tpl_src is None or tpl_prov is None:
        print("  ❌ 配置模板缺失（provider_sources / provider 结构不对）")
        return 1

    new_src = json.loads(json.dumps(tpl_src))
    new_src.update({"id": src_id, "provider": src_id, "type": stype,
                    "provider_type": "chat_completion", "key": api_key,
                    "api_base": api_base, "enable": True})
    # 替换掉旧的同 id 条目
    d["provider_sources"] = [s for s in srcs
                             if not (isinstance(s, dict)
                                     and s.get("id") == src_id)] + [new_src]

    new_prov = json.loads(json.dumps(tpl_prov))
    new_prov.update({"id": f"{src_id}/{model}", "provider_source_id": src_id,
                     "model": model, "enable": True, "max_context_tokens": 65536})
    d["provider"] = [p for p in provs
                     if not (isinstance(p, dict)
                             and p.get("provider_source_id") == src_id)] + [new_prov]
    save_json(CMD_CONFIG, d)
    print(f"  ✔ 模型已配置（{nm} / {model}）")

    io.open(KBMARK, "w", encoding="utf-8").write(
        "配置完成于 " + __import__("datetime").datetime.now().isoformat() + "\n")

    print()
    line("═")
    print("  ✅ 配置完成")
    print()
    print("  接下来：双击「启动 Akasha.bat」")
    print("  首次启动 AstrBot 约需 40~90 秒，请等它自动打开面板。")
    line("═")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
