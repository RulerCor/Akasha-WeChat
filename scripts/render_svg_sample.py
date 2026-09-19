# -*- coding: utf-8 -*-
"""把测试 SVG 渲染成 PNG 并保存，供 read_image 人工复核渲染质量。"""
import base64
import shutil
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

p = ob_protocol._decode_base64_image(base64.b64encode(SVG).decode())
print("产物:", p)
if p and p.endswith(".png"):
    shutil.copy2(p, "release/verify/svg_render_quality.png")
    import os
    os.unlink(p)
    print("已保存 → release/verify/svg_render_quality.png")
elif p:
    print("降级为 .svg（渲染不可用）:", p)
