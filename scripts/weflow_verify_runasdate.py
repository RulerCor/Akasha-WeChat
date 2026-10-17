"""
WeFlow RunAsDate 启动后的自动验证脚本。
判断标准：/api/v1/messages（读历史，依赖 WCDB）
  - 200  -> 数据库恢复，-101 已被时间回拨绕过
  - 500  -> 仍然 WCDB 未连接（RunAsDate 对这个 Electron 应用无效）
  - 拒连 -> WeFlow 没起来或 HTTP API 未启用
"""
import json
import sys
import urllib.parse
import urllib.request
import urllib.error

CONFIG = r"runtime/bridge/config.json"

def main():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    base = cfg.get("weflow_base_url", "http://127.0.0.1:5031").rstrip("/")
    token = cfg.get("access_token", "")
    # 先拿一个真实 talker（联系人接口不依赖 WCDB，一定能通）
    try:
        req = urllib.request.Request(base + "/api/v1/contacts",
                                     headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=8) as r:
            contacts = json.load(r).get("contacts", [])
        talker = next((c["username"] for c in contacts if c["username"].endswith("@chatroom")),
                      contacts[0]["username"] if contacts else "filehelper")
    except Exception as e:
        print(f"[X] WeFlow 没连上（{e}）：可能还没启动完，或 HTTP API 未启用")
        sys.exit(1)

    url = f"{base}/api/v1/messages?talker={urllib.parse.quote(talker)}&limit=1"
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=8) as r:
            body = json.load(r)
        n = len(body.get("messages", []))
        print(f"[OK] 数据库已恢复！-101 绕过成功（GET messages -> 200，读到 {n} 条历史）")
        print("     注意：WeFlow 内部时钟=2026-09-30，它界面/导出的时间戳会显示成那天，属正常。")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:120]
        except Exception:
            pass
        if e.code == 500:
            print(f"[FAIL] 仍然 500：{detail}")
            print("       RunAsDate 对这个 Electron 应用没生效（Chromium 多进程可能绕过了钩子）。")
            print("       备选：以管理员身份改系统时间到 2026-09-30 手动对照验证；")
            print("       或等作者修复 / 修补 DLL（见 GitHub issue #1226/#1227）。")
        else:
            print(f"[?] HTTP {e.code}：{detail}")
    except Exception as e:
        print(f"[X] 验证请求失败：{e}")

if __name__ == "__main__":
    main()
