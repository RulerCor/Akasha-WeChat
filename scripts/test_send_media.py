# -*- coding: utf-8 -*-
"""媒体外发实测：把「文件 + 图片」真的发到微信「文件传输助手」。

用途
----
用户反馈「让 bot 画 SVG，它说画了却没发出来」。代码路径看起来是通的
（send_message_to_user 支持 file/image → 桥接 file/image 段 → UiaSender.send_file/send_image），
但必须**真机验证**。

为什么用「文件传输助手」
------------------------
它是自发自收的会话，发错了也不会打扰任何人，是最安全的测试靶子。

用法
----
    runtime/bridge/.venv/Scripts/python.exe scripts/test_send_media.py
    runtime/bridge/.venv/Scripts/python.exe scripts/test_send_media.py --only file
    runtime/bridge/.venv/Scripts/python.exe scripts/test_send_media.py --only image
"""
import io
import os
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BRIDGE = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge"
sys.path.insert(0, BRIDGE)

TARGET = "文件传输助手"
ONLY = None
if "--only" in sys.argv:
    ONLY = sys.argv[sys.argv.index("--only") + 1]

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 160" width="240" height="160">
  <rect width="240" height="160" fill="#fdf6e3"/>
  <circle cx="120" cy="70" r="46" fill="#d6336e" opacity="0.85"/>
  <ellipse cx="120" cy="70" rx="70" ry="30" fill="none" stroke="#6a4a52" stroke-width="3"/>
  <text x="120" y="146" font-size="14" text-anchor="middle" fill="#6a4a52">Mon3tr 椭球笔触测试</text>
</svg>
"""

# 1x1 -> 用 Pillow 生成一张 64x64 渐变 PNG，确保是有效图片
def make_png(path):
    try:
        from PIL import Image
    except ImportError:
        return False
    im = Image.new("RGB", (64, 64))
    px = im.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (x * 4, y * 4, 180)
    im.save(path)
    return True


def weflow_recent(talker, limit=4):
    import requests
    import config
    try:
        r = requests.get(config.WE_FLOW_BASE_URL + "/api/v1/messages",
                         params={"access_token": config.ACCESS_TOKEN,
                                 "talker": talker, "limit": limit}, timeout=8)
        d = r.json()
        return d if isinstance(d, list) else (d.get("messages") or [])
    except Exception as e:
        print(f"    （WeFlow 复核失败: {e}）")
        return []


def main():
    from uia_sender import UiaSender

    print("=" * 68)
    print(f"媒体外发实测 | 目标={TARGET} | only={ONLY}")
    print("=" * 68)

    s = UiaSender(search_enabled=True)
    s._init()
    if not s._ensure_window():
        print("❌ 找不到微信窗口")
        return 1
    s._activate()

    tmp_files = []
    ok_all = True

    try:
        # ---- 文件 (SVG) ----
        if ONLY in (None, "file"):
            fd, svg_path = tempfile.mkstemp(suffix=".svg")
            os.close(fd)
            with io.open(svg_path, "w", encoding="utf-8") as f:
                f.write(SVG)
            tmp_files.append(svg_path)
            print(f"\n[1] send_file → {TARGET}")
            print(f"    源文件: {svg_path} ({os.path.getsize(svg_path)} B)")
            r = s.send_file(TARGET, svg_path)
            print(f"    send_file 返回: {r}")
            ok_all = ok_all and bool(r)
            time.sleep(2)

        # ---- 图片 (PNG) ----
        if ONLY in (None, "image"):
            fd, png_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            tmp_files.append(png_path)
            if not make_png(png_path):
                print("\n[2] ⚠️ 没有 Pillow，跳过图片测试")
            else:
                print(f"\n[2] send_image → {TARGET}")
                print(f"    源文件: {png_path} ({os.path.getsize(png_path)} B)")
                r = s.send_image(TARGET, png_path)
                print(f"    send_image 返回: {r}")
                ok_all = ok_all and bool(r)
                time.sleep(2)

        # ---- WeFlow 复核 ----
        print(f"\n[3] WeFlow 复核 talker=filehelper 最近消息")
        for m in weflow_recent("filehelper", 5):
            t = time.strftime("%m-%d %H:%M:%S",
                              time.localtime(int(m.get("createTime") or 0)))
            nm = os.path.basename(str(m.get("content") or ""))
            print(f"    {t} isSend={m.get('isSend')} | {nm[:70]}")

    finally:
        for p in tmp_files:
            try:
                os.unlink(p)
            except Exception:
                pass

    print()
    print("结果:", "✅ 发送调用均成功（请对照上面 WeFlow 是否出现同名文件）"
          if ok_all else "❌ 有发送失败")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
