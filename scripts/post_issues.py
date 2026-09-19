# -*- coding: utf-8 -*-
"""把 release/issues/ 下的两篇 issue 草稿提交到对应 GitHub 仓库。

用 REST API（gh 的 GraphQL 已超限，REST 正常）。
token 从 git credential（wincred）读取，不回显、不落盘。
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def get_token():
    p = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, timeout=30,
    )
    for line in (p.stdout or "").splitlines():
        if line.startswith("password="):
            return line[len("password="):].strip()
    raise SystemExit("找不到 GitHub 凭据")


TOKEN = get_token()


def api(url, payload=None, method="GET"):
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "akasha-rc-issue-bot")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, body


def load(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    title = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def post(repo, path, label):
    title, body = load(path)
    print("=" * 66)
    print(f"[{label}] -> {repo}")
    print(f"  标题: {title}")
    print(f"  正文: {len(body)} 字符")
    status, res = api(f"https://api.github.com/repos/{repo}/issues",
                      {"title": title, "body": body}, "POST")
    if status in (200, 201):
        print(f"  ✅ 已提交: {res.get('html_url')}")
        print(f"     编号: #{res.get('number')}")
        return res.get("html_url")
    print(f"  ❌ HTTP {status}")
    print(f"     {str(res)[:500]}")
    return None


if __name__ == "__main__":
    results = []
    results.append(post(
        "alingalingling/Akasha-WeChat",
        "release/issues/issue_akasha_whitelist.md",
        "Akasha-Wechat 白名单三缺陷"))
    results.append(post(
        "AstrBotDevs/AstrBot",
        "release/issues/issue_astrbot_kb_wording.md",
        "AstrBot 知识库措辞"))
    print()
    print("=" * 66)
    for u in results:
        print(" ", u or "(失败)")
