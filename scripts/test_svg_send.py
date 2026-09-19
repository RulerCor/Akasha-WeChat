# -*- coding: utf-8 -*-
"""验证画图发送链路修复：SVG 能转成位图，失败能降级，不假报成功。"""
import base64
import os
import sys

sys.path.insert(0, "runtime/bridge")
sys.stdout.reconfigure(encoding="utf-8")

import ob_protocol  # noqa: E402

SVG = b'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 420" width="320" height="420">
  <defs>
    <radialGradient id="bg" cx="50%" cy="42%" r="65%">
      <stop offset="0%" stop-color="#f7f1e8"/><stop offset="100%" stop-color="#e5d9c9"/>
    </radialGradient>
  </defs>
  <rect width="320" height="420" fill="url(#bg)"/>
  <ellipse cx="160" cy="150" rx="90" ry="110" fill="#fff"/>
  <circle cx="128" cy="130" r="9" fill="#2e7d32"/>
  <circle cx="192" cy="130" r="9" fill="#2e7d32"/>
  <path d="M130 180 Q160 205 190 180" stroke="#c2185b" stroke-width="4" fill="none"/>
  <text x="160" y="300" text-anchor="middle" font-size="22" fill="#5a4a52">M3</text>
</svg>'''

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

results = []

# ── 用例 1：位图 PNG 原样通过 ──
p = ob_protocol._decode_base64_image(base64.b64encode(PNG_1PX).decode())
ok = p and p.endswith(".png") and os.path.exists(p)
os.unlink(p) if p and os.path.exists(p) else None
results.append(("位图 PNG 原样落盘", ok))

# ── 用例 2：SVG → 渲染成 PNG（本机 Chromium）──
p = ob_protocol._decode_base64_image(base64.b64encode(SVG).decode())
ok = False
if p:
    if p.endswith(".png") and "render" in os.path.basename(p):
        ok = True
        print(f"  SVG 渲染产物: {os.path.basename(p)}  {os.path.getsize(p)}B")
        os.unlink(p)
    elif p.endswith(".svg"):
        print(f"  渲染失败，降级保留 .svg（{os.path.getsize(p)}B）——降级路径可用")
    os.unlink(p) if os.path.exists(p) else None
results.append(("SVG 处理（渲染或降级）", ok))

# ── 用例 3：渲染产物可被 PIL 识别（UIA 发送的前提）──
p = ob_protocol._decode_base64_image(base64.b64encode(SVG).decode())
if p and p.endswith(".png"):
    from PIL import Image
    with Image.open(p) as im:
        size = im.size
    os.unlink(p)
    results.append((f"渲染产物 PIL 可识别 {size}", True))
elif p:
    os.unlink(p) if os.path.exists(p) else None
    results.append(("渲染产物 PIL 可识别", False))
else:
    results.append(("渲染产物 PIL 可识别", False))

print()
print("=" * 56)
allok = True
for name, ok in results:
    print(f"  {'✅' if ok else '❌'} {name}")
    allok = allok and ok
print()
print("✅ 全部通过" if allok else "❌ 有失败")
sys.exit(0 if allok else 1)
