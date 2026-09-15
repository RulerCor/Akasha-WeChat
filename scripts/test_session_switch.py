# -*- coding: utf-8 -*-
"""验证「会话切换 + 发送」修复（2026-09-15 串会话事故回归测试）。

做法：
  1. 先把微信切到「文件传输助手」（故意停在一个"错误"的会话上）
  2. 用 state.get_contact() 把 OneBot ID 解析成真实会话名（修复点 A）
  3. 调 send_text() 发给目标 —— 修复点 B 保证它**必须**先真正切过去，
     切不过去就放弃发送（绝不发到当前打开的会话）
  4. 提示用 WeFlow 复核消息到底落在哪个会话

用法：
    python scripts/test_session_switch.py 1000000001        # 发到某人私聊（默认）
    python scripts/test_session_switch.py 2000000001 --dry  # 只解析+试切换，不发送
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BRIDGE = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge"
sys.path.insert(0, BRIDGE)

OID = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000001
DRY = "--dry" in sys.argv

import state          # noqa: E402
from uia_sender import UiaSender  # noqa: E402

TEXT = "【会话切换测试】这条应该出现在这里，而不是当前打开的会话喵。"


def main():
    print("=" * 64)
    print(f"会话切换回归测试 | 目标 OneBot ID = {OID} | {'只解析' if DRY else '真发送'}")
    print("=" * 64)

    s = UiaSender(search_enabled=True)
    s._init()
    if not s._ensure_window():
        print("❌ 找不到微信窗口")
        return 1
    s._activate()

    # 1) 故意先停在一个错误会话上
    print("\n[1] 先把微信切到「文件传输助手」（制造发错会话的条件）")
    if s._switch_to_contact("文件传输助手"):
        time.sleep(0.6)
        print(f"    当前会话: {s._current_chat_title()!r}")
    else:
        print("    ⚠️ 切不过去，继续（当前会话可能就是别的）")

    # 2) 解析目标名
    print(f"\n[2] state.get_contact({OID}) 解析目标会话名")
    name = state.get_contact(OID, str(OID))
    print(f"    → {name!r}")
    if name == str(OID):
        print("    ❌ 仍是原始 ID（解析失败，修复没生效？）")
        return 1

    if DRY:
        print("\n[3] 只试切换（不发消息）")
        ok = s._switch_to_contact(name)
        time.sleep(0.6)
        cur = s._current_chat_title()
        print(f"    切换结果={ok} | 当前会话={cur!r}")
        print("    " + ("✅ 切换成功" if s._is_chat_open(name) else "❌ 切换后仍未命中"))
        return 0 if s._is_chat_open(name) else 2

    # 3) 真发送（走修复后的 send_text）
    print(f"\n[3] send_text 发给 {name!r}")
    ok = s.send_text(name, TEXT)
    time.sleep(0.8)
    cur = s._current_chat_title()
    print(f"    发送返回={ok} | 发送后当前会话={cur!r}")

    # 4) 找出 WeFlow 里这个会话的键，方便复核
    import requests
    import config
    try:
        if OID in state.known_groups() or str(OID) in [
                str(state._wxid_to_int(r)) for r in state.known_groups()]:
            pass
        room = None
        for r in state.known_groups():
            if state._wxid_to_int(r) == OID:
                room = r
                break
        if room:
            talker = room
        else:
            talker = None
            for wxid, info in state.all_persons().items():
                if info.get("uid") == OID:
                    talker = wxid
                    break
        print(f"\n[4] WeFlow 复核键 talker={talker!r}")
        if talker:
            r = requests.get(config.WE_FLOW_BASE_URL + "/api/v1/messages",
                             params={"access_token": config.ACCESS_TOKEN,
                                     "talker": talker, "limit": 3}, timeout=8)
            d = r.json()
            ms = d if isinstance(d, list) else (d.get("messages") or [])
            for m in ms[:3]:
                t = time.strftime("%m-%d %H:%M",
                                  time.localtime(int(m.get("createTime") or 0)))
                print(f"    {t} isSend={m.get('isSend')} | {str(m.get('content'))[:50]}")
    except Exception as e:
        print(f"    （复核失败: {e}）")

    print("\n✅ 测试完成" if ok else "\n❌ 发送被拒绝（切不过去时这是正确行为）")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
