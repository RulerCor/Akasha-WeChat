# -*- coding: utf-8 -*-
"""生成一个 AstrBot Dashboard API Key（scopes 限定 kb/file/data）。

为什么存在：知识库导入脚本需要走 Dashboard API（进程外无法直接驱动
AstrBot 内核——循环导入+依赖完整启动环境）。而 Dashboard 登录密码
只有用户知道；api_keys 表则支持本地直接管理。

安全性：key 明文只写入 runtime/astrbot/data/kb_api_key.txt（已在
.gitignore 的 runtime/ 覆盖范围内，不入库不入发行版）。
用法：python scripts/create_kb_api_key.py
"""
import hashlib
import io
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "runtime", "astrbot", "data", "data_v4.db")


def hash_key(raw: str) -> str:
    # 与 astrbot/dashboard/services/api_key_service.py 完全一致
    return hashlib.pbkdf2_hmac(
        "sha256", raw.encode("utf-8"), b"astrbot_api_key", 100_000,
    ).hex()


def main() -> int:
    raw = "abk_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    c = sqlite3.connect(DB)
    cols = [r[1] for r in c.execute("pragma table_info(api_keys)")]
    row = {
        "created_at": now, "updated_at": now, "inner_id": None,
        "key_id": secrets.token_hex(8), "name": "kb-import-script",
        "key_hash": hash_key(raw), "key_prefix": raw[:12],
        "scopes": '["kb", "file", "data"]', "created_by": "akasha-scripts",
        "last_used_at": None, "expires_at": None, "revoked_at": None,
    }
    c.execute(
        f"insert into api_keys ({', '.join(cols)}) "
        f"values ({', '.join('?' for _ in cols)})",
        [row.get(k) for k in cols],
    )
    c.commit()
    c.close()

    out = os.path.join(ROOT, "runtime", "astrbot", "data", "kb_api_key.txt")
    io.open(out, "w", encoding="utf-8").write(raw)
    print("✅ 已创建 API key（scopes: kb/file/data）")
    print("   明文保存于:", out)
    print("   key_prefix:", raw[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
