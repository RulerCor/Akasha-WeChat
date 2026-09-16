# -*- coding: utf-8 -*-
"""给 AstrBot 前端语言包（内嵌在 dist/assets/index-*.js）注入 active_reply.blacklist 条目。

背景：AstrBot 会把 CONFIG_METADATA 里的 description/hint 转成 i18n key
（ext_group.ltm.<path>.description），真正显示的文字来自前端语言包。
只加 Python 侧 schema 不够，必须同步补语言包，否则面板会显示原始 key。

注意：dist/assets 下有多个 index-*.js，**只有主 bundle**（体积最大的那个，
内含 active_reply / whitelist 语言包）才有注入点。其余小 chunk 不含锚点，
本脚本会自动跳过、不写文件、不留备份。

用法:
    python patch_astrbot_i18n_blacklist.py            # 注入（幂等）
    python patch_astrbot_i18n_blacklist.py --verify   # 只检查，不写任何文件
    python patch_astrbot_i18n_blacklist.py --revert   # 从最近备份还原
"""
import io
import os
import sys
import glob
import shutil

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DIST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "astrbot",
    ".venv", "Lib", "site-packages", "astrbot", "dashboard", "dist", "assets")

PAIRS = [
    # 中文
    ('whitelist:{description:"主动回复白名单",hint:"为空时不启用白名单过滤。使用 /sid 获取 ID。"}',
     ',blacklist:{description:"主动回复黑名单",hint:"黑名单内的会话绝不主动回复，优先级高于白名单。使用 /sid 获取 ID。"}'),
    # English
    ('whitelist:{description:"Active Reply Whitelist",hint:"Whitelist filtering is disabled when empty. Use /sid to get IDs."}',
     ',blacklist:{description:"Active Reply Blacklist",hint:"Conversations here never get proactive replies. Takes priority over the whitelist. Use /sid to get IDs."}'),
    # Русский
    ('whitelist:{description:"Белый список для активных ответов",hint:"Фильтрация отключена, если список пуст. Используйте /sid для получения ID."}',
     ',blacklist:{description:"Чёрный список для активных ответов",hint:"Сессии из чёрного списка никогда не получают активных ответов. Имеет приоритет над белым списком. Используйте /sid для получения ID."}'),
    # 日本語
    ('whitelist:{description:"プロアクティブ返信のホワイトリスト",hint:"空欄の場合、ホワイトリストによる絞り込みは無効です。/sid で ID を取得できます。"}',
     ',blacklist:{description:"プロアクティブ返信のブラックリスト",hint:"ブラックリスト内のセッションには絶対にプロアクティブ返信しません。ホワイトリストより優先されます。/sid で ID を取得できます。"}'),
]

MARK = "blacklist:{description:"
BAK_SUFFIX = ".bak_20260914_i18n"


def find_bundle():
    """返回含语言包锚点的主 bundle 路径（取体积最大的候选）。"""
    cands = []
    for f in glob.glob(os.path.join(DIST, "index-*.js")):
        if ".bak" in f:
            continue
        try:
            s = io.open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "active_reply" in s:
            cands.append((len(s), f))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


def main():
    argv = sys.argv[1:]
    revert = "--revert" in argv
    verify_only = "--verify" in argv

    if revert:
        files = [f for f in glob.glob(os.path.join(DIST, "index-*.js.bak_*"))]
        if not files:
            print("❌ 没有备份可还原")
            return 1
        for bak in files:
            target = bak.split(".bak_")[0]
            shutil.copyfile(bak, target)
            print(f"  ↩️ {os.path.basename(target)}  <-  {os.path.basename(bak)}")
        print("\n完成。刷新 AstrBot 面板（Ctrl+F5 强制刷新）查看效果。")
        return 0

    bundle = find_bundle()
    if not bundle:
        print("❌ 没找到含语言包的主 bundle（dist/assets/index-*.js）")
        return 1

    name = os.path.basename(bundle)
    s = io.open(bundle, encoding="utf-8", errors="replace").read()
    already = s.count(MARK)
    missing = [old[:34] for old, _ in PAIRS if s.count(old) != 1]

    print(f"主 bundle: {name}  ({len(s)} 字节)")

    if verify_only:
        if already >= 4:
            print(f"补丁状态: ✅ 已打（{already} 处 blacklist 条目）")
            return 0
        if already:
            print(f"补丁状态: ⚠️ 只注入 {already}/4 处，建议重打")
            return 1
        print("补丁状态: ❌ 未打（面板会显示原始 i18n key）")
        return 1

    if already >= 4:
        print(f"  ℹ️ 已注入过（{already} 处），跳过")
        print("\n完成。刷新 AstrBot 面板（Ctrl+F5 强制刷新）查看效果。")
        return 0

    if missing:
        print(f"  ⚠️ {len(missing)} 个锚点未唯一匹配（上游 bundle 可能已变更）: {missing}")

    ok = 0
    for old, add in PAIRS:
        if s.count(old) == 1:
            s = s.replace(old, old + add, 1)
            ok += 1

    if ok == 0:
        # 一个都没匹配上：不写文件、不留备份，避免污染上游包
        print("  ❌ 注入 0/4，未修改文件（锚点对不上，需按新 bundle 更新 PAIRS）")
        return 1

    bak = bundle + BAK_SUFFIX
    if not os.path.exists(bak):
        shutil.copyfile(bundle, bak)
        print(f"  已备份 -> {os.path.basename(bak)}")

    io.open(bundle, "w", encoding="utf-8", newline="").write(s)
    print(f"  ✅ 注入 {ok}/4 种语言，新大小 {len(s)} 字节")
    print("\n完成。刷新 AstrBot 面板（Ctrl+F5 强制刷新）查看效果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
