# -*- coding: utf-8 -*-
"""给 AstrBot 前端语言包（内嵌在 dist/assets/index-*.js）注入 active_reply.blacklist 条目。

背景：AstrBot 会把 CONFIG_METADATA 里的 description/hint 转成 i18n key
（ext_group.ltm.<path>.description），真正显示的文字来自前端语言包。
只加 Python 侧 schema 不够，必须同步补语言包，否则面板会显示原始 key。

用法: python patch_astrbot_i18n_blacklist.py [--revert]
"""
import io, os, sys, glob, shutil

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


def main():
    revert = "--revert" in sys.argv
    files = [f for f in glob.glob(os.path.join(DIST, "index-*.js"))
             if ".bak" not in f]
    if not files:
        print("❌ 没找到 dist/assets/index-*.js")
        return 1

    for f in files:
        s = io.open(f, encoding="utf-8", errors="replace").read()
        print(f"\n文件: {os.path.basename(f)}  ({len(s)} 字节)")

        if revert:
            baks = glob.glob(f + ".bak_*")
            if not baks:
                print("  ❌ 没有备份可还原")
                continue
            shutil.copyfile(sorted(baks)[-1], f)
            print(f"  ↩️ 已从 {os.path.basename(sorted(baks)[-1])} 还原")
            continue

        already = s.count(MARK)
        if already >= 4:
            print(f"  ℹ️ 已注入过（{already} 处），跳过")
            continue

        # 备份一次
        bak = f + ".bak_20260914_i18n"
        if not os.path.exists(bak):
            shutil.copyfile(f, bak)
            print(f"  已备份 -> {os.path.basename(bak)}")

        ok = 0
        for old, add in PAIRS:
            n = s.count(old)
            if n == 1:
                s = s.replace(old, old + add, 1)
                ok += 1
            else:
                print(f"  ⚠️ 匹配 {n} 次: {old[:30]}...")
        io.open(f, "w", encoding="utf-8", newline="").write(s)
        print(f"  ✅ 注入 {ok}/4 种语言，新大小 {len(s)} 字节")

    print("\n完成。刷新 AstrBot 面板（Ctrl+F5 强制刷新）查看效果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
