"""
配置模块：加载 config.json，提供全局配置常量。
"""

import json
import os
import logging
import threading

# ============ 本地请求一律绕过系统代理 ============
#
# 桥接要访问的 WeFlow(5031)、Ollama(11434)、AstrBot(11229) 全在本机。
# 如果机器上设了 HTTP_PROXY（很常见，比如 VPN/代理软件），requests 会把
# 127.0.0.1 的请求也发给代理，导致 502/连接失败。这里在**代码层面**兜底，
# 不依赖启动脚本是否设置了 NO_PROXY。
for _var in ("NO_PROXY", "no_proxy"):
    _cur = os.environ.get(_var, "")
    _missing = [h for h in ("127.0.0.1", "localhost", "::1") if h not in _cur]
    if _missing:
        os.environ[_var] = ",".join(filter(None, [_cur] + _missing))

# ============ 配置 ============

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
EXAMPLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(EXAMPLE_FILE):
            import shutil
            shutil.copy2(EXAMPLE_FILE, CONFIG_FILE)
            print(f"[配置] 检测到 config.json 不存在，已从 config.example.json 自动创建")
        else:
            raise FileNotFoundError(f"既没有 config.json，也没有 config.example.json")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()

WE_FLOW_BASE_URL = config["weflow_base_url"]
ACCESS_TOKEN = config["access_token"]
BRIDGE_DIR = os.path.dirname(CONFIG_FILE)
# 项目根 = 桥接目录的上一级（例如 Akasha-Wechat_RC/runtime/ 下的 bridge/ → runtime/）。
# 所有相对路径都以它为基准，这样整个目录拷贝到任何电脑、任何位置都能直接用。
PROJECT_ROOT = os.path.abspath(os.path.join(BRIDGE_DIR, ".."))

# ============ 项目标识（长期可识别） ============
PROJECT_NAME = "Akasha-WeChat_RC"
_VERSION_FILE = os.path.join(BRIDGE_DIR, "VERSION")
try:
    with open(_VERSION_FILE, encoding="utf-8") as _f:
        PROJECT_VERSION = _f.read().strip() or "0.0.0"
except Exception:
    PROJECT_VERSION = "0.0.0"


def _resolve_dir_or_file(value: str, sub_path: str) -> str:
    """把配置里的路径解析成绝对路径。

    - 绝对路径：原样使用；
    - 相对路径：以 PROJECT_ROOT 为基准（找不到再试 BRIDGE_DIR）；
    - 没配置：按常见布局自动搜索（runtime/astrbot、同级 AstrBot、上一级 astrbot…）。

    这样"搬到别的电脑/别的盘"时不用改任何配置。
    """
    cands: list[str] = []
    if value:
        if os.path.isabs(value):
            cands.append(value)
        else:
            cands.append(os.path.normpath(os.path.join(PROJECT_ROOT, value)))
            cands.append(os.path.normpath(os.path.join(BRIDGE_DIR, value)))
    else:
        for base in (PROJECT_ROOT, os.path.dirname(PROJECT_ROOT)):
            for name in ("astrbot", "AstrBot"):
                cands.append(os.path.join(base, name, *sub_path.split("/")))
            cands.append(os.path.join(base, *sub_path.split("/")))
    for c in cands:
        if c and os.path.exists(c):
            return c
    # 都没找到：返回第一个候选（相对路径配置时以 PROJECT_ROOT 为基准）
    return cands[0] if cands else ""


ASTRBOT_ATTACHMENTS = _resolve_dir_or_file(
    config.get("astrbot_attachments", ""), "data/attachments")
BOT_NICKNAMES = config["bot_nicknames"]
BOT_WXID = config.get("bot_wxid", "")
SEND_METHOD = config.get("send_method", "weflow_api")
WE_FLOW_SEND_API = config["weflow_send_api"]
BUFFER_SECONDS = config.get("buffer_seconds", 5)
WEB_PORT = config.get("web_port", 8766)
WEB_HOST = config.get("web_host", "0.0.0.0")
# 群聊模式："all"（标准：所有消息转发，@ 必回、非 @ 由 AstrBot 随机插话决定）/"batch"（整群合并）。
# 旧值 "mention"（仅@回复）已并入 all：是否对非 @ 消息插话完全由 AstrBot 的
# active_reply（随机插话）开关与概率决定，桥接不再有第二种普通模式。
# 兼容：老配置里的 "mention" 在读取时归一化为 "all"。
GROUP_REPLY_MODE = config.get("group_reply_mode", "all")
if GROUP_REPLY_MODE == "mention":
    GROUP_REPLY_MODE = "all"

# 切换联系人的方式：
#   "auto"   —— 先在左侧会话列表按名字点击，找不到再退回 Ctrl+F 搜索（默认）
#   "list"   —— 只用会话列表点击
#   "search" —— 只用 Ctrl+F 搜索
SWITCH_METHOD = config.get("switch_method", "auto")

# 是否记录「被过滤掉的」消息（语音/表情/未@机器人的群消息等）。
# 打开后日志里能看到消息确实收到了、只是被策略丢弃，便于区分「没收到」和「被跳过」。
LOG_SKIPPED_MESSAGES = config.get("log_skipped_messages", True)

# 引用回复前缀（〔回复 某某：原文〕）。微信 UIA 无法做原生引用气泡，只能文本模拟；
# 默认关闭 —— 关闭后 reply 段直接忽略，回复为纯文本。
QUOTE_REPLY_PREFIX = config.get("quote_reply_prefix", False)

# 群聊图片读取门槛（秒）：图片必须和「同一个人的 @」属于同一次请求才读取。
#   - @ 之前发的图：暂存这么长时间，等同一人发 @ 文本时一并读取
#   - @ 之后紧跟着的图：IMAGE_AFTER_MENTION_WINDOW 内立即读取
# 私聊图片不受影响，始终读取。
IMAGE_MENTION_WINDOW = config.get("image_mention_window", 120)

# @ 之后多久内发的图视为同一次请求（覆盖缓冲 5s + 手速间隔）
IMAGE_AFTER_MENTION_WINDOW = max(20, config.get("buffer_seconds", 5) * 3)

# 单张图片大小上限（字节）。超过则跳过并在日志说明，防止异常大图拖垮 WebSocket。
IMAGE_MAX_BYTES = int(config.get("image_max_bytes", 8 * 1024 * 1024))

# 图片理解的路子（两种都保留，按下面的开关二选一）：
#   ① 桥接侧描述（本节下面的 IMAGE_CAPTION_*）：桥接先把图转成文字再发。
#   ② 原样转交（默认）：桥接把图片作为标准 OneBot image 段发出（base64://），
#      AstrBot 侧按其自身配置处理 ——「图片转述模型」留空则直接用主模型（多模态）看。

# AstrBot OneBot 连接配置（bridge 作为 WebSocket 客户端连 AstrBot 的 aiocqhttp 服务端）
ASTRBOT_OB_URL = config.get("astrbot_ob_url", "ws://127.0.0.1:19777")

# AstrBot 主配置（cmd_config.json）路径：面板「成员与权限」要往这里同步
# 管理员列表和白名单/主动回复设置。留空则按常见布局自动搜索（见 _resolve_dir_or_file）。
ASTRBOT_CONFIG_FILE = _resolve_dir_or_file(
    config.get("astrbot_config_file", ""), "data/cmd_config.json")

# 图片描述配置（支持 ollama 或 openai 兼容 API）
IMAGE_CAPTION_PROVIDER = config.get("image_caption_provider", "ollama")  # "ollama" / "openai"
IMAGE_CAPTION_MODEL = config.get("image_caption_model", "llava:7b")
IMAGE_CAPTION_API_KEY = config.get("image_caption_api_key", "")
IMAGE_CAPTION_API_BASE = config.get("image_caption_api_base", "https://api.xiaomimimo.com/v1")
IMAGE_CAPTION_PROMPT = config.get("image_caption_prompt", "请用中文简短描述这张图片的内容")

# Ollama 图片描述配置（provider=ollama 时使用）
OLLAMA_BASE_URL = config.get("ollama_base_url", "http://127.0.0.1:61000")
OLLAMA_TIMEOUT = config.get("ollama_timeout", 60)

# 是否启用「桥接侧图片描述」：
#   在 config.json 里**显式填了** image_caption_model 才启用（走上面的描述配置）；
#   留空则走默认路径 —— 图片原样交给 AstrBot，由它（主模型/转述模型）决定怎么看。
IMAGE_CAPTION_ENABLED = bool((config.get("image_caption_model") or "").strip())

# ============ 日志 ============

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("bridge.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("ob11-bridge")
