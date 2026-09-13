"""成员与管理员管理：面板数据源 + 与 AstrBot 配置（cmd_config.json）的双向同步。

管理员模型（v1.0.1-rc.3 起）：
  - 桥接维护 data/admins.json（真实 wxid 列表）作为唯一事实来源；
  - user_id = md5(wxid)，同一个人在私聊和所有群里是同一个 ID，
    所以管理员只需登记一次，处处生效；
  - 保存时自动把 wxid 映射成 UID 写进 AstrBot 的 admins_id。
    注意：AstrBot 只在启动时把 admins_id 读进内存对象，
    写文件后需重启 AstrBot（或在它的 WebUI 里再存一次）才生效。
"""

import json
import logging
import os

import config
import state

log = logging.getLogger("ob11-bridge")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")


# ============ 管理员名单（桥接侧） ============


def load_admins() -> list:
    """读取管理员 wxid 列表（保持顺序、去重）。"""
    try:
        with open(ADMINS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("wxids", [])
        return [str(w).strip() for w in (data or []) if str(w).strip()]
    except Exception:
        return []


def save_admins(wxids) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    uniq = list(dict.fromkeys(str(w).strip() for w in wxids if str(w).strip()))
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)


# ============ AstrBot 配置文件读写（保留 BOM） ============


def _astrbot_cfg_path() -> str:
    return getattr(config, "ASTRBOT_CONFIG_FILE", "") or ""


def _read_astrbot_cfg():
    """返回 (cfg dict, 是否带 BOM)。文件不存在抛 FileNotFoundError。"""
    path = _astrbot_cfg_path()
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"AstrBot 配置不可用: {path or '(未配置)'}")
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return json.loads(raw.decode("utf-8-sig")), bom


def _write_astrbot_cfg(cfg, bom: bool) -> None:
    path = _astrbot_cfg_path()
    data = json.dumps(cfg, ensure_ascii=False, indent=4).encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as f:
        f.write(data)


def _platform_id(cfg: dict) -> str:
    """从 AstrBot 配置里找 aiocqhttp 平台的平台 ID（拼 UMO 用）。"""
    platforms = cfg.get("platform") or []
    if isinstance(platforms, dict):
        platforms = [platforms]
    for p in platforms:
        if isinstance(p, dict) and "aiocqhttp" in str(p.get("type", "")):
            return str(p.get("id") or "wechat_bridge")
    for p in platforms:
        if isinstance(p, dict) and p.get("id"):
            return str(p["id"])
    return "wechat_bridge"


# ============ 同步 ============


def sync_admins_to_astrbot(wxids=None):
    """把管理员 wxid 映射成 UID 写入 AstrBot admins_id。

    返回 (是否写入成功, 说明文本)。同时总是更新桥接侧 admins.json。
    """
    if wxids is None:
        wxids = load_admins()
    else:
        save_admins(wxids)
    uids = [str(state._wxid_to_int(w)) for w in wxids if w]
    try:
        cfg, bom = _read_astrbot_cfg()
    except Exception as e:
        log.warning(f"同步管理员失败：{e}")
        return False, str(e)
    old = cfg.get("admins_id") or []
    cfg["admins_id"] = uids
    try:
        _write_astrbot_cfg(cfg, bom)
    except Exception as e:
        log.warning(f"写入 AstrBot admins_id 失败：{e}")
        return False, str(e)
    log.info(f"🔑 管理员已同步到 AstrBot：{old} -> {uids}（重启 AstrBot 后生效）")
    return True, f"已写入 {len(uids)} 个管理员（原 {len(old)} 个）"


def read_overview() -> dict:
    """面板「成员与权限」页所需的一切数据。"""
    admins = set(load_admins())
    bot_key = (config.BOT_WXID or "").strip()
    persons = []
    for wxid, p in state.all_persons().items():
        if bot_key and (wxid == bot_key or wxid.startswith(bot_key)):
            continue  # 机器人自己不入列
        names = p.get("names") or []
        persons.append({
            "wxid": wxid,
            "name": names[0] if names else wxid,
            "uid": p.get("uid"),
            "admin": wxid in admins,
        })
    persons.sort(key=lambda x: (not x["admin"], x["name"]))

    cfg = {}
    astrbot_ok = False
    try:
        cfg, _ = _read_astrbot_cfg()
        astrbot_ok = True
    except Exception as e:
        cfg_err = str(e)

    ps = cfg.get("platform_settings") or {}
    ltm = (cfg.get("provider_ltm_settings") or {}).get("active_reply") or {}
    groups = []
    pid = _platform_id(cfg) if astrbot_ok else "wechat_bridge"
    for session, name in sorted(state.known_groups().items(), key=lambda kv: kv[1]):
        gid = state._wxid_to_int(session)
        groups.append({
            "session": session,
            "name": name,
            "gid": gid,
            "umo": f"{pid}:GroupMessage:{gid}",
        })

    return {
        "ok": True,
        "astrbot_available": astrbot_ok,
        "astrbot_path": _astrbot_cfg_path() or "(未配置)",
        "astrbot_error": "" if astrbot_ok else cfg_err,
        "persons": persons,
        "groups": groups,
        "admins": sorted(admins),
        "id_whitelist_enable": bool(ps.get("enable_id_white_list", False)),
        "id_whitelist": ps.get("id_whitelist") or [],
        "ar_enable": bool(ltm.get("enable", False)),
        "ar_possibility": ltm.get("possibility_reply", 0.1),
        "ar_whitelist": ltm.get("whitelist") or [],
    }


def update_astrbot_settings(payload: dict):
    """按面板提交更新 AstrBot 的白名单 / 主动回复设置。

    只动这几个键，其余配置一律不碰。返回 (成功?, 说明)。
    """
    try:
        cfg, bom = _read_astrbot_cfg()
    except Exception as e:
        return False, str(e)

    ps = cfg.setdefault("platform_settings", {})
    if "id_whitelist_enable" in payload:
        ps["enable_id_white_list"] = bool(payload["id_whitelist_enable"])
    if "id_whitelist" in payload:
        ps["id_whitelist"] = [str(x).strip() for x in payload["id_whitelist"] if str(x).strip()]

    ltm = cfg.setdefault("provider_ltm_settings", {})
    ar = ltm.setdefault("active_reply", {})
    if "ar_enable" in payload:
        ar["enable"] = bool(payload["ar_enable"])
    if "ar_possibility" in payload:
        try:
            ar["possibility_reply"] = max(0.0, min(1.0, float(payload["ar_possibility"])))
        except (TypeError, ValueError):
            pass
    if "ar_whitelist" in payload:
        ar["whitelist"] = [str(x).strip() for x in payload["ar_whitelist"] if str(x).strip()]

    try:
        _write_astrbot_cfg(cfg, bom)
    except Exception as e:
        return False, str(e)
    log.info("⚙️ AstrBot 白名单/主动回复设置已由面板更新（重启 AstrBot 后生效）")
    return True, "已写入 AstrBot 配置"
