# -*- coding: utf-8 -*-
"""引用（quote）探测 v5 —— 参照 Mon3trBot v1.7.4 的做法

Mon3trBot v1.7.4 的 send_quote() 关键两步（src/wechat_client.py:2325）：
    1. msg_obj.roll_into_view()      # 先滚动到可视区，避免按旧坐标引用到别的消息
    2. msg_obj.quote(text)           # wxauto4 内部 = 右键 + 选菜单「引用」

本脚本在 Akasha 桥接这边做对应的探测：
  A. 定位会话最后一条消息，打印它的类名/名字/矩形
  B. 右键前先确保它可见（滚到底 + 必要时滚入视图）
  C. 右键后枚举「新的顶层窗口」，重点找 Win32 标准菜单类 **#32768**
     （标准右键菜单就是这个类名；之前的探测只找"新增窗口"，很可能漏了它）
  D. 找到菜单就列出全部菜单项，看有没有「引用」

只读模式（默认）只探测、不点击菜单、不发消息：
    python scripts/probe_quote5.py 文件传输助手
    python scripts/probe_quote5.py 文件传输助手 --do     # 真的点「引用」并发送测试文本
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BRIDGE = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge"
sys.path.insert(0, BRIDGE)

import uiautomation as auto  # noqa: E402

CONTACT = sys.argv[1] if len(sys.argv) > 1 else "文件传输助手"
DO_IT = "--do" in sys.argv


def top_windows():
    out = []
    for w in auto.GetRootControl().GetChildren():
        try:
            if not w.Exists(0):
                continue
            out.append((w.Name or "", w.ClassName or "", w.ProcessId))
        except Exception:
            pass
    return out


def rect_of(ctrl):
    try:
        r = ctrl.BoundingRectangle
        return (r.left, r.top, r.right, r.bottom, r.width(), r.height())
    except Exception:
        return None


def find_in(ctrl, keyword, depth=0, maxd=9, budget=None, path=""):
    """在子树里找 Name 含关键字的控件，返回 (控件, 路径)"""
    if budget is None:
        budget = [400]
    if depth > maxd or budget[0] <= 0:
        return None
    try:
        for c in ctrl.GetChildren():
            budget[0] -= 1
            if budget[0] <= 0:
                return None
            try:
                nm = (c.Name or "").strip()
                ct = c.ControlTypeName or ""
            except Exception:
                continue
            p = path + "/" + (nm or ct)
            if keyword in nm:
                return (c, p)
            r = find_in(c, keyword, depth + 1, maxd, budget, p)
            if r:
                return r
    except Exception:
        pass
    return None


def main():
    print("=" * 70)
    print(f"引用探测 v5 | 目标会话: {CONTACT} | 模式: {'执行' if DO_IT else '只读'}")
    print("=" * 70)

    from uia_sender import UiaSender

    s = UiaSender(search_enabled=True)
    s._init()
    if not s._ensure_window():
        print("❌ 找不到微信窗口（需要先打开微信）")
        return 1
    s._activate()
    print(f"✅ 微信窗口: {s._window.Name!r} / {s._window.ClassName!r}")

    if not s._is_chat_open(CONTACT):
        print(f"… 切到会话 '{CONTACT}'")
        if not s._switch_to_contact(CONTACT):
            print(f"❌ 切不过去（会话名对吗？）")
            return 1
    print(f"✅ 当前会话: {s._current_chat_title()!r}")
    time.sleep(0.5)

    if "--seed" in sys.argv:
        seed = "引用测试-1（这条用来测试右键引用）"
        print(f"\n[0] 先发一条种子消息到 '{CONTACT}': {seed}")
        try:
            s.send_text(CONTACT, seed + "\n" + seed)
            time.sleep(2.0)
        except Exception as e:
            print(f"    发送失败: {e}")
            return 1

    for _try in range(3):
        lst = s._find_message_list()
        if lst:
            kids = list(lst.GetChildren())
            if kids:
                break
        time.sleep(0.8)

    kids = list(lst.GetChildren()) if lst else []
    items = [c for c in kids if s.MSG_ITEM_CLASS in ((c.ClassName or ""))]
    print(f"✅ 消息项（按 {s.MSG_ITEM_CLASS!r} 过滤）: {len(items)} 条 / 子节点共 {len(kids)}")
    items = [c for c in kids if s.MSG_ITEM_CLASS in ((c.ClassName or ""))]
    print(f"✅ 消息项（按 {s.MSG_ITEM_CLASS!r} 过滤）: {len(items)} 条 / 子节点共 {len(kids)}")
    if not items and kids:
        print("   ⚠️ 过滤后为空，打印全部子节点的类名（用于定位真实类名）:")
        from collections import Counter
        for cls, n in Counter((c.ClassName or "(空)") for c in kids).most_common(12):
            print(f"      {n:3d} × {cls}")
        items = [c for c in kids
                 if ("Item" in (c.ClassName or "") or "Msg" in (c.ClassName or ""))]
        print(f"   → 放宽为含 Item/Msg 的类名后: {len(items)} 条")
    if not items:
        return 1

    # 取最后 3 条看看
    for it in items[-3:]:
        r = rect_of(it)
        nm = (it.Name or "").replace("\n", " ")[:60]
        print(f"   - {it.ClassName} | {nm!r} | rect={r}")

    item = items[-1]
    r = rect_of(item)
    print(f"\n▶ 目标消息 rect={r}")
    print("  └ 子元素（找气泡）:")
    try:
        for i, c in enumerate(item.GetChildren()):
            cr = rect_of(c)
            nm = (c.Name or "").replace("\n", " ")[:40]
            print(f"     [{i}] {c.ClassName!r} | {c.ControlTypeName} | {nm!r} | {cr}")
    except Exception as e:
        print(f"     枚举失败: {e}")

    # === mon3trbot 关键差异 1：先确保可见（滚到底 / 滚入视图）===
    print("\n[1] 确保消息可见（滚到底）")
    for meth in ("_scroll_message_list_to_bottom", "_scroll_to_bottom"):
        fn = getattr(s, meth, None)
        if callable(fn):
            try:
                fn()
                print(f"    调用了 {meth}()")
            except Exception as e:
                print(f"    {meth}() 失败: {e}")
            break
    else:
        print("    （无滚动方法，跳过）")
    try:
        item.MoveCursorToMyCenter(simulateMove=False)
        time.sleep(0.2)
        print("    已把光标移到消息中心（等价 roll_into_view 的一半）")
    except Exception as e:
        print(f"    MoveCursorToMyCenter 失败: {e}")
    time.sleep(0.4)

    # 菜单候选词（右键菜单里通常一起出现的兄弟项）
    BROTHERS = ("复制", "转发", "收藏", "删除", "撤回", "引用", "多选", "提醒")

    def scan_menu():
        """在微信主窗口内部 + 所有顶层窗口里找右键菜单的词"""
        hits = []
        targets = [s._window] + list(auto.GetRootControl().GetChildren())
        for t in targets:
            try:
                if not t.Exists(0):
                    continue
            except Exception:
                continue
            for kw in BROTHERS:
                got = find_in(t, kw, budget=[250])
                if got:
                    c, p = got
                    if (c.ControlTypeName or "") in ("MenuItemControl", "ListItemControl",
                                                     "ButtonControl", "TextControl",
                                                     "CustomControl"):
                        hits.append((kw, c.Name, c.ControlTypeName, p[:90]))
        return hits

    print("\n[2b] 右键前的菜单词基线（避免把常驻控件误判成菜单）")
    base_hits = set((h[0], h[1]) for h in scan_menu())
    print(f"     基线命中 {len(base_hits)} 项: {sorted(base_hits)[:6]}")

    before = set(top_windows())
    print(f"\n[2] 右键前顶层窗口 {len(before)} 个")

    # 横向扫描：item 横跨整行，中点是空白，气泡通常靠一侧
    if r and "--sweep" in sys.argv:
        left, top, right, bottom, w, h = r
        y = (top + bottom) // 2
        xs = []
        for frac in (0.12, 0.25, 0.4, 0.5, 0.6, 0.75, 0.88):
            xs.append(int(left + w * frac))
        print(f"\n[3] 横向扫描右键（y={y}）")
        for i, x in enumerate(xs, 1):
            try:
                auto.RightClick(x, y)
            except Exception as e:
                print(f"   x={x} 右键失败: {e}")
                continue
            time.sleep(0.7)
            nw = [w2 for w2 in top_windows() if w2 not in before]
            mh = [h2 for h2 in scan_menu() if (h2[0], h2[1]) not in base_hits]
            menu32768 = any(w2[1] == "#32768" for w2 in nw)
            flag = "★★★" if (mh or menu32768 or nw) else "—"
            print(f"   [{i}] x={x:4d} {flag} 新窗口={len(nw)} 新菜单词={len(mh)}")
            for h2 in mh[:5]:
                print(f"         {h2[0]!r} → {h2[1]!r} ({h2[2]})")
            if mh or menu32768:
                print("   ✅ 找到菜单，停止扫描")
                hit = None
                for h2 in mh:
                    if h2[0] == "引用":
                        hit = mh[mh.index(h2)]
                        break
                break
            # 关掉可能残留的菜单：点一下消息列表空白处
            try:
                auto.Click(int(left + w * 0.5), max(0, top - 20))
            except Exception:
                pass
            time.sleep(0.3)
        else:
            print("   ❌ 全部位置都没出现菜单")
            print("\n结论：当前微信版本的右键菜单对 UIA 不可见（自绘），原生引用走不通")
            return 2
    else:
        print("\n[3] 右键消息项…")
        try:
            item.RightClick()
            print("    item.RightClick() 已执行")
        except Exception as e:
            print(f"    item.RightClick() 失败: {e}")
            if r:
                cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
                try:
                    auto.RightClick(cx, cy)
                    print(f"    回退 auto.RightClick({cx},{cy})")
                except Exception as e2:
                    print(f"    回退也失败: {e2}")
                    return 1
        time.sleep(1.0)

    # === 右键后快照：找新窗口，重点 #32768 ===
    after = top_windows()
    new = [w for w in after if w not in before]
    print(f"\n[4] 右键后新出现的顶层窗口 {len(new)} 个")
    for n, c, p in new:
        mark = "  ★★★ Win32 标准菜单!" if c == "#32768" else ""
        print(f"     {c!r} | {n[:40]!r} | pid={p}{mark}")

    menu_win = None
    for w in auto.GetRootControl().GetChildren():
        try:
            if not w.Exists(0):
                continue
            if (w.ClassName or "") == "#32768":
                menu_win = w
                break
        except Exception:
            pass

    hit = None
    if menu_win is not None:
        print(f"\n✅ 找到标准菜单窗口 #32768")
        try:
            for i, c in enumerate(menu_win.GetChildren()):
                nm = (c.Name or "").strip()
                ct = c.ControlTypeName or ""
                print(f"   [{i}] {ct} | {nm!r}")
                if "引用" in nm:
                    hit = c
        except Exception as e:
            print(f"   枚举菜单项失败: {e}")
    else:
        print("\n⚠️ 没有 #32768 菜单窗口 —— 全树搜「引用」")
        for w in auto.GetRootControl().GetChildren():
            try:
                if not w.Exists(0):
                    continue
            except Exception:
                continue
            found = find_in(w, "引用", budget=[400])
            if found:
                c, p = found
                print(f"   命中: {(c.Name or '')!r}")
                print(f"   路径: {p[:200]}")
                print(f"   窗口: {(w.ClassName or '')!r} / {(w.Name or '')[:30]!r}")
                hit = c
                break

    # === 执行：走一遍真正的生产代码路径 ===
    print("\n[5] 执行：_right_click_until_menu() → 点「引用」→ 输入 → 发送")
    picked = s._right_click_until_menu(item)
    if picked is None:
        print("❌ 生产方法也没弹出菜单（会被降级普通发送）")
        return 3
    print(f"   ✅ 菜单已定位: {(picked.Name or '')!r} / {picked.ControlTypeName}")
    try:
        picked.Click()
    except Exception:
        try:
            s._click_control_center(picked)
        except Exception as e:
            print(f"❌ 点击菜单项失败: {e}")
            return 3
    time.sleep(0.6)
    if not s._locate_input():
        print("❌ 找不到输入框")
        return 3
    txt = "【引用功能测试】这条是带引用的回复喵"
    from uia_sender import set_value
    if not (set_value(s._input_control, "") and set_value(s._input_control, txt)):
        import pyperclip
        s._click_input_center()
        pyperclip.copy(txt)
        time.sleep(0.1)
        auto.SendKeys("{Ctrl}v")
    time.sleep(0.2)
    if s._send_current(s._input_control, verify=False):
        print(f"✅ 引用消息已发送: {txt}")
        return 0
    print("❌ 发送失败")
    return 3


if __name__ == "__main__":
    sys.exit(main())
