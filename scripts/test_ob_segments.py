# -*- coding: utf-8 -*-
"""ob_protocol 出站处理回归测试（2026-09-16）。

覆盖本轮修的几类问题：
  A) 纯空白段不再发出「空气泡」，且它携带的引用会并入下一段正文
  A2) @ 段转文字后会并入正文（不单独成条），且不与引用冲突
  B) 只有 reply 段（没有正文）时不发送任何东西
  C) 空文本段不发送
  D) 同一调用内多段严格按链序发送（跨调用顺序由 ob_client 队列保证）
  E) base64 图片段 → send_image 被调用
  F) file:// 文件段 → 路径正确还原 + send_file 被调用
     （「任何文件都要能发出去」这条的验证）

用桥接 venv 跑：
  runtime/bridge/.venv/Scripts/python.exe scripts/test_ob_segments.py
"""
import asyncio
import io
import os
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import ob_protocol  # noqa: E402
import state        # noqa: E402

GID = 2000000001
# 1x1 透明 PNG
PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
           "z8AAAwAB/wFPh5JzAAAAAElFTkSuQmCC")


class Recorder:
    def __init__(self):
        self.calls = []

    def send_text(self, contact, text):
        self.calls.append(("text", text))
        return True

    def send_quote(self, contact, quote_content, text):
        self.calls.append(("quote", text, quote_content))
        return True

    def send_image(self, contact, path):
        self.calls.append(("image", os.path.basename(path)))
        return True

    def send_file(self, contact, path):
        self.calls.append(("file", os.path.basename(path)))
        return True


class FakeWS:
    async def send(self, payload):
        pass


def T(t):
    return {"type": "text", "data": {"text": t}}


def chain(rec, message):
    rec.calls.clear()
    asyncio.run(ob_protocol._handle_ob_api({
        "action": "send_group_msg",
        "params": {"group_id": GID, "message": message},
        "echo": {"seq": 1},
    }))
    return list(rec.calls)


def main():
    state.sender_instance = Recorder()
    state._ob_ws = FakeWS()
    state.get_message = lambda mid: {"content": "原消息内容", "sender": "洛辰"}
    rec = state.sender_instance

    print("quote_reply_native =", ob_protocol.config.QUOTE_REPLY_NATIVE)
    print("=" * 74)
    ok_all = True

    def check(title, cond, detail=""):
        nonlocal ok_all
        ok_all = ok_all and bool(cond)
        print(f"{'✅' if cond else '❌'} {title}")
        if not cond:
            print(f"      实际: {detail}")

    # A) 空白段 + 引用，后面才是正文
    got = chain(rec, [
        {"type": "reply", "data": {"id": 1}},
        T("   \n  "),
        T("正文甲"),
        T("正文乙"),
    ])
    check("A1 空白段不产生空气泡（共 2 条）", len(got) == 2, got)
    check("A2 引用并入第一段正文（且未被空白段吃掉）",
          len(got) == 2 and got[0][0] == "quote" and got[0][1].endswith("正文甲")
          and got[0][2] == "原消息内容", got)
    check("A3 后续段不带引用", len(got) == 2 and got[1] == ("text", "正文乙"), got)
    check("A4 没有任何发送是空白内容",
          all(c[-1].strip() for c in got), got)

    # A2) 打开 @ 转文字，验证 @ 与正文合并
    ob_protocol.config.MENTION_AS_TEXT = True
    got = chain(rec, [
        {"type": "at", "data": {"qq": "1000000013"}},
        T("   "),
        T("正文"),
    ])
    check("A5 @ 段转文字后并入正文、不单独成条（共 1 条）",
          len(got) == 1 and got[0][0] == "text" and got[0][1].startswith("@")
          and got[0][1].endswith("正文"), got)
    ob_protocol.config.MENTION_AS_TEXT = False

    # B) 只有 reply 段
    got = chain(rec, [{"type": "reply", "data": {"id": 1}}])
    check("B 只有引用段 → 不发送（不发空气泡）", got == [], got)

    # C) 空文本 / 纯空白
    check("C 空文本段 → 不发送",
          chain(rec, [T("")]) == [] and chain(rec, [T("  \n ")]) == [])

    # D) 链内顺序
    got = chain(rec, [T("第一段"), T("第二段"), T("第三段")])
    check("D 链内顺序严格保持",
          got == [("text", "第一段"), ("text", "第二段"), ("text", "第三段")], got)

    # E) base64 图片
    got = chain(rec, [{"type": "image", "data": {"file": "base64://" + PNG_B64}}])
    check("E base64 图片 → 调用 send_image",
          len(got) == 1 and got[0][0] == "image", got)

    # F) file:// 文件
    fd, fpath = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    with io.open(fpath, "w", encoding="utf-8") as f:
        f.write("<svg xmlns='http://www.w3.org/2000/svg'/>")
    uri = "file:///" + fpath.replace("\\", "/")
    got = chain(rec, [{"type": "file", "data": {"file": uri, "name": "monalisa.svg"}}])
    check("F file:// 文件 → 调用 send_file",
          len(got) == 1 and got[0] == ("file", os.path.basename(fpath)), got)
    try:
        os.unlink(fpath)
    except Exception:
        pass

    print()
    print("结果:", "✅ 全部通过" if ok_all else "❌ 存在失败")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
