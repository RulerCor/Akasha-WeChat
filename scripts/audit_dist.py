# -*- coding: utf-8 -*-
"""发行版最终审计：隐私 / 人格 / 启动器 / 安装包 / 四项改动。"""
import json
import os
import sqlite3
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

ZIP = "release/dist/Akasha_RulerCordelius-Wechatbot-v1.5.1.zip"
z = zipfile.ZipFile(ZIP)
N = z.namelist()

print("=" * 62)
print("v1.5.1 发行版最终审计")
print("=" * 62)
print(f"条目数: {len(N)}   大小: {os.path.getsize(ZIP)/1048576:.1f} MB")
print()

# 1) 隐私
print("=== 1) 隐私残留 ===")
NAME = "Junqin" + " Zhao"
PATHFRAG = "Users\\" + "Junqin"
hits = []
for n in N:
    if "/site-packages/" in n or "/.venv/" in n:
        continue
    if not n.endswith((".py", ".json", ".md", ".bat", ".cfg", ".txt", ".yml", ".yaml")):
        continue
    try:
        t = z.read(n).decode("utf-8", "ignore")
    except Exception:
        continue
    for kw in (NAME, PATHFRAG, "JunqinZhao"):
        if kw in t:
            hits.append((n, kw))
print(f"  本机姓名/路径命中: {len(hits)}  {'✅' if not hits else '❌'}")
for n, kw in hits[:8]:
    print("   ", n, kw)

# 2) cmd_config 密钥
print()
print("=== 2) provider 密钥 ===")
cfg = json.loads(z.read([n for n in N if n.endswith("astrbot/data/cmd_config.json")][0]).decode("utf-8"))
leak = 0
for p in cfg.get("provider_sources", []):
    k = p.get("key") or ""
    hdr = p.get("custom_headers") or {}
    if len(k) > 20:
        print(f"  ❌ {p.get('id')} key={k[:20]}"); leak += 1
    for hk, hv in hdr.items():
        if "Bearer" in str(hv) or (len(str(hv)) > 30 and "auth" in hk.lower()):
            print(f"  ❌ {p.get('id')} {hk}={str(hv)[:20]}"); leak += 1
print(f"  密钥泄漏: {leak}  {'✅' if leak == 0 else '❌'}")

# 3) 人格
print()
print("=== 3) 人格（软件资产，必须保留）===")
tmp = os.path.join(tempfile.gettempdir(), "audit.db")
open(tmp, "wb").write(z.read([n for n in N if n.endswith("astrbot/data/data_v4.db")][0]))
c = sqlite3.connect(tmp)
rows = [r[0] for r in c.execute("select persona_id from personas")]
c.close()
print(f"  {rows}  {'✅' if len(rows) >= 4 else '❌'}")

# 4) 普通知识库文档
print()
print("=== 4) 普通知识库文档 ===")
kb = [n for n in N if "kb_docs/" in n]
print(f"  {len(kb)} 个  {'✅' if kb else '❌'}")

# 5) 向量知识库应删除
print()
print("=== 5) 向量知识库（应已删）===")
vec = [n for n in N if "knowledge_base" in n and n.endswith((".db", ".faiss"))]
print(f"  {len(vec)} 个  {'✅' if not vec else '❌'}")

# 6) 启动器
print()
print("=== 6) 启动器 ===")
for f in ("启动 Akasha.bat", "停止 Akasha.bat", "使用说明.md", "BUILD_INFO.md"):
    print(f"  {'✅' if any(n.endswith(f) for n in N) else '❌'} {f}")

# 7) 安装包
print()
print("=== 7) 安装包 ===")
for n in N:
    if "/installers/" in n and n.lower().endswith((".exe", ".zip")):
        print(f"  ✅ {n.split('/')[-1]}  ({z.getinfo(n).file_size/1048576:.0f} MB)")

# 8) 四项改动
print()
print("=== 8) 今晚四项改动 ===")
checks = [
    ("一键重启按钮", "akasha/web_panel.py",
     ["abRestartBtn", "restartAstrbot", "api/astrbot-restart", "api/astrbot-status"]),
    ("进程控制模块", "akasha/astrbot_ctl.py",
     ["DETACHED_PROCESS", "find_astrbot_pids", "restart_async", "_astrbot_root", "astrbot.lock"]),
    ("白名单显示修复", "akasha/web_panel.py", ["wlEntryToUid", "wlUidSet"]),
    ("白名单规整去重", "akasha/people.py", ["normalize_whitelist_entries", "covered_uids"]),
]
ok_all = True
for label, rel, kws in checks:
    full = [n for n in N if n.endswith(rel)]
    if not full:
        print(f"  ❌ {label}: 缺 {rel}"); ok_all = False; continue
    t = z.read(full[0]).decode("utf-8", "ignore")
    miss = [k for k in kws if k not in t]
    print(f"  {'✅' if not miss else '❌'} {label}" + (f"  缺 {miss}" if miss else ""))
    if miss:
        ok_all = False

# 9) 使用说明含白名单坑
t = z.read([n for n in N if n.endswith("使用说明.md")][0]).decode("utf-8")
print()
print("=== 9) 使用说明是否含白名单坑 ===")
for kw in ("只有某个好友不回", "手写裸数字", "必须用面板"):
    print(f"  {'✅' if kw in t else '❌'} {kw}")

print()
print("=" * 62)
print("结论:", "✅ 全部通过" if (not hits and leak == 0 and ok_all and len(rows) >= 4) else "❌ 有问题，见上")
