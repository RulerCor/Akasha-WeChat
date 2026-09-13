"""
uia_sender.py — 基于 Windows UI Automation 的微信 4.0+ 消息发送器
=================================================================

原理：
  微信 4.0 基于 Electron (Chromium)。Chromium 通过 UIA 桥将 HTML 输入元素
  暴露为标准 UIA 控件。通过 ValuePattern 设置输入框文本，InvokePattern 点击
  发送按钮。全程无鼠标键盘模拟，无 DLL 注入，风控风险极低。

工作流：
  1. 定位微信 4.0 窗口 (Electron/Chromium)
  2. 搜索联系人 → 点击匹配项 → 切换到目标聊天
  3. 定位聊天输入框 (EditControl + ValuePattern)
  4. 设置文本 → 点击发送按钮或 Enter
  5. 图片通过剪贴板粘贴后发送

依赖:
  pip install uiautomation pyperclip
  发送图片需要 Pillow: pip install Pillow
"""

import logging
import os
import re
import subprocess
import threading
import time

log = logging.getLogger("weflow-bridge")


def name_of(ctrl) -> str:
    """安全读取控件 Name（部分 mmui 控件会抛异常）。"""
    try:
        return (ctrl.Name or "")[:30]
    except Exception:
        return "?"


def set_value(ctrl, text: str) -> bool:
    """用 ValuePattern 设置控件文本。

    uiautomation >= 2.0.29 同时移除了 Control.SetValue，
    必须走 GetValuePattern().SetValue()，否则会 AttributeError，
    退化到 SendKeys 后文字会打进「当前有焦点的控件」（常见是搜索框）。
    """
    try:
        ctrl.GetValuePattern().SetValue(text)
        return True
    except Exception as e:
        log.debug(f"ValuePattern.SetValue 失败: {e}")
        return False


def _pattern_available(ctrl, property_name: str) -> bool:
    """判断控件是否支持某个 UI Automation 模式。

    uiautomation >= 2.0.29 移除了 Control.IsXxxPatternAvailable 快捷属性，
    直接访问会抛 AttributeError，必须用 PropertyId + GetPropertyValue 查询。
    """
    try:
        import uiautomation as auto
        prop = getattr(auto.PropertyId, property_name, None)
        if prop is None:
            return False
        return bool(ctrl.GetPropertyValue(prop))
    except Exception:
        return False


VALUE_PATTERN_PROP = "IsValuePatternAvailableProperty"
INVOKE_PATTERN_PROP = "IsInvokePatternAvailableProperty"


class BaseSender:
    """消息发送器基类"""
    def send_text(self, contact: str, text: str) -> bool:
        raise NotImplementedError

    def send_image(self, contact: str, image_path: str) -> bool:
        raise NotImplementedError


class UiaSender(BaseSender):
    """
    基于 Windows UI Automation 的微信 4.0+ 发送器

    对微信 4.0 (Electron/Chromium) 优化：
      - 自动检测 Electron 架构
      - ValuePattern 直接设值（非键盘模拟）
      - InvokePattern 精确点击发送按钮
      - 自动联系人搜索切换

    Attributes:
        search_enabled: 是否自动搜索联系人（默认 True，False 则需手动切到聊天窗口）
    """

    # 微信 4.x 的窗口标题会变（未打开会话时是「微信」，打开后是「Weixin」或会话名）
    WECHAT_TITLES = ["微信", "WeChat", "Weixin"]

    EXCLUDE_CLASSES = ["Chrome_WidgetWin_1", "CabinetWClass"]

    # 微信 4.x (mmui) 控件类名
    CHAT_INPUT_CLASS = "ChatInputField"     # 聊天输入框，位于控件树第 18 层左右
    SEARCH_BOX_MARKERS = ("Validator", "Search", "搜索")  # 搜索框，绝不能当输入框用

    # 左侧会话列表：ListControl(mmui::XTableView) → ListItemControl(mmui::ChatSessionCell)
    # 每项的 Name 形如 "联系人名\n预览内容\n时间"，第一行即联系人名
    SESSION_LIST_CLASS = "XTableView"
    SESSION_ITEM_CLASS = "ChatSessionCell"

    @staticmethod
    def _is_search_box(ctrl) -> bool:
        """判断控件是否为搜索框（微信 4.x 里它是唯一一个浅层 EditControl）。"""
        try:
            cls = ctrl.ClassName or ""
            name = ctrl.Name or ""
            return any(m in cls or m == name for m in UiaSender.SEARCH_BOX_MARKERS)
        except Exception:
            return False

    def __init__(self, search_enabled: bool = True):
        self._lock = threading.Lock()
        self._auto = None
        self._ready = False

        # 微信窗口
        self._window = None
        self._is_electron = False  # True=4.0+, False=3.9

        # 控件缓存
        self._search_box = None
        self._input_control = None
        self._send_button = None
        self._session_list = None
        self._title_bar = None
        self._last_contact = ""
        self._use_coord_fallback = False

        self.search_enabled = search_enabled

        self._init()

    # ================================================================
    # 初始化
    # ================================================================

    def _init(self):
        """初始化 UIA 并定位窗口"""
        try:
            import uiautomation as auto
            self._auto = auto
        except ImportError:
            log.error("请先安装 uiautomation: pip install uiautomation")
            return

        log.info("正在搜索微信窗口...")
        self._find_window()
        if self._window:
            log.info(f"微信窗口: '{self._window.Name}' ClassName={self._window.ClassName}")
            self._ready = True

    def _find_window(self):
        """按标题搜索微信窗口"""
        auto = self._auto
        root = auto.GetRootControl()
        for w in root.GetChildren():
            cls = w.ClassName
            if cls in self.EXCLUDE_CLASSES:
                continue
            for kw in self.WECHAT_TITLES:
                if kw in w.Name:
                    self._window = w
                    if cls != "WeChatMainWndForPC":
                        self._is_electron = True
                    return

    # ================================================================
    # 控件定位
    # ================================================================

    def _ensure_window(self) -> bool:
        """确保窗口可用"""
        if not self._ready:
            return False
        if self._window and self._window.Exists(0.2):
            return True
        self._find_window()
        if not self._window:
            log.warning("微信窗口未找到")
            self._ready = False
            return False
        return True

    def _hwnd(self) -> int:
        """微信主窗口的 Win32 句柄。

        微信 4.x 的 Win32 类名仍是 Qt51514QWindowIcon（UIA 里报 mmui::MainWindow），
        优先用 UIA 控件的 NativeWindowHandle，最可靠。
        """
        try:
            if self._window:
                h = self._window.NativeWindowHandle
                if h:
                    return h
        except Exception:
            pass
        import ctypes
        for cls in ("Qt51514QWindowIcon", "WeChatMainWndForPC",
                    "mmui::MainWindow"):
            h = ctypes.windll.user32.FindWindowW(cls, None)
            if h:
                return h
        return 0

    def _activate(self):
        """激活微信窗口到前台（AttachThreadInput 确保后台也能生效）"""
        try:
            self._window.SetActive()
            time.sleep(0.3)
        except Exception:
            try:
                self._window.SwitchToThisWindow()
                time.sleep(0.3)
            except Exception:
                pass
        # AttachThreadInput 绕过 Windows 后台进程不能 SetForegroundWindow 的限制
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = self._hwnd()
            if hwnd:
                WE_CHAT_TID = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
                CURRENT_TID = ctypes.windll.kernel32.GetCurrentThreadId()
                ctypes.windll.user32.AttachThreadInput(CURRENT_TID, WE_CHAT_TID, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.BringWindowToTop(hwnd)
                ctypes.windll.user32.AttachThreadInput(CURRENT_TID, WE_CHAT_TID, False)
        except Exception:
            pass

    def _click_input_center(self) -> bool:
        """物理点击聊天输入框正中心，确保键盘焦点在输入框上。

        用于没有 ValuePattern、只能靠 SendKeys/剪贴板输入的兜底路径——
        如果不先点击，按键会打进当时拥有焦点的控件（往往就是搜索框）。
        """
        try:
            ctrl = self._input_control
            if ctrl is None:
                return False
            rect = ctrl.BoundingRectangle
            if not rect:
                return False
            x = rect.left + rect.width() // 2
            y = rect.top + rect.height() // 2
            import ctypes
            ctypes.windll.user32.SetCursorPos(x, y)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
            time.sleep(0.25)
            return True
        except Exception as e:
            log.debug(f"点击输入框失败: {e}")
            return False

    def _dump_tree(self, ctrl, depth: int = 0, max_depth: int = 4):
        """调试: 输出 UIA 子树（仅 debug）"""
        if depth > max_depth:
            return
        try:
            pad = "  " * depth
            name = (ctrl.Name or "")[:40]
            cls = ctrl.ClassName or ""
            ctrl_type = ctrl.ControlTypeName
            vp = _pattern_available(ctrl, VALUE_PATTERN_PROP)
            ip = _pattern_available(ctrl, INVOKE_PATTERN_PROP)
            rect = ctrl.BoundingRectangle
            info = f"[{rect.left},{rect.top} {rect.width()}x{rect.height()}]" if rect else ""
            log.debug(f"{pad}{ctrl_type} '{name}' {info} V={vp} I={ip} cls={cls}")
            for child in ctrl.GetChildren():
                self._dump_tree(child, depth + 1, max_depth)
        except Exception:
            pass

    def _find_search_box_uia(self):
        """
        通过 UIA 树定位微信搜索框。

        微信 4.x (Qt/Electron) 的搜索框特征：
        - EditControl 类型
        - 窗口上半部分 (top < 30% 窗口高度)
        - 宽度小于窗口一半（区别于底部的聊天输入框）
        - 宽度大于 50px（排除小控件）
        """
        auto = self._auto
        win_rect = self._window.BoundingRectangle
        win_w = win_rect.width()
        win_h = win_rect.height()

        edits = []

        def walk(ctrl, depth=0):
            if depth > 12:
                return
            try:
                for child in ctrl.GetChildren():
                    if child.ControlTypeName == "EditControl":
                        rect = child.BoundingRectangle
                        if rect and rect.width() > 50:
                            edits.append((child, rect))
                    walk(child, depth + 1)
            except Exception:
                pass

        try:
            walk(self._window)
        except Exception:
            pass

        # 过滤：上半部分的 EditControl，宽度小于窗口一半
        candidates = [
            (c, r) for c, r in edits
            if r.top < win_rect.top + win_h * 0.3 and r.width() < win_w * 0.5
        ]

        if not candidates:
            return None

        # 取最靠上的（搜索框通常比任何其他上半部分控件更高）
        candidates.sort(key=lambda x: x[1].top)
        return candidates[0][0]

    def _focus_chat_input(self):
        """
        物理点击聊天输入框区域（坐标后备模式专用）。
        让聊天输入框获得键盘焦点。
        """
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return

        hwnd = self._hwnd()
        if not hwnd:
            return

        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        input_x = rect.left + int(win_w * 0.3)
        input_y = rect.top + int(win_h * 0.92)
        ctypes.windll.user32.SetCursorPos(input_x, input_y)
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.3)

    # ================================================================
    # 左侧会话列表：按名字定位并点击
    # ================================================================

    def _find_session_list(self):
        """定位左侧会话列表 ListControl（mmui::XTableView）。"""
        if not self._ensure_window():
            return None

        if self._session_list is not None:
            try:
                self._session_list.GetChildren()
                return self._session_list
            except Exception:
                self._session_list = None

        found = []

        def walk(ctrl, depth=0):
            if depth > 30 or found:
                return
            try:
                for ch in ctrl.GetChildren():
                    try:
                        if (ch.ControlTypeName == "ListControl"
                                and self.SESSION_LIST_CLASS in (ch.ClassName or "")):
                            found.append(ch)
                            return
                    except Exception:
                        pass
                    walk(ch, depth + 1)
            except Exception:
                pass

        try:
            walk(self._window)
        except Exception as e:
            log.debug(f"遍历会话列表异常: {e}")

        if not found:
            log.debug("未找到会话列表控件（mmui::XTableView）")
            return None

        self._session_list = found[0]
        return self._session_list

    def _iter_session_items(self):
        """返回当前可见的会话列表项（mmui::ChatSessionCell）。"""
        lst = self._find_session_list()
        if lst is None:
            return []
        items = []
        try:
            for it in lst.GetChildren():
                try:
                    if (it.ControlTypeName == "ListItemControl"
                            and self.SESSION_ITEM_CLASS in (it.ClassName or "")
                            and it.BoundingRectangle):
                        items.append(it)
                except Exception:
                    pass
        except Exception as e:
            log.debug(f"读取会话列表项异常: {e}")
        return items

    @staticmethod
    def _session_title(item) -> str:
        """取会话项的第一行作为标题（Name 形如 '名字\\n预览\\n时间'）。"""
        try:
            name = item.Name or ""
        except Exception:
            return ""
        return name.split("\n")[0].strip()

    @staticmethod
    def _normalize_contact(s: str) -> str:
        """归一化联系人名：去首尾空白/不可见字符，去掉尾部 '(数字)'，去掉中间空格。"""
        if not s:
            return ""
        s = s.strip().replace("\u200b", "").replace("\xa0", " ")
        s = re.sub(r"\s*\(\d+\)\s*$", "", s)
        return re.sub(r"\s+", "", s)

    def _find_session_item(self, contact: str):
        """在当前可见的会话项里找匹配 contact 的项。返回 (item, 匹配等级) 或 (None, -1)。"""
        want = self._normalize_contact(contact)
        if not want:
            return None, -1

        best, best_rank = None, -1
        for it in self._iter_session_items():
            title = self._normalize_contact(self._session_title(it))
            if not title:
                continue
            if title == want:
                rank = 3
            elif title.startswith(want) or want.startswith(title):
                rank = 2
            elif want in title or title in want:
                rank = 1
            else:
                continue
            if rank > best_rank:
                best, best_rank = it, rank
                if rank == 3:
                    break
        return best, best_rank

    def _click_control_center(self, ctrl) -> bool:
        """用真实鼠标点击控件中心（mmui 列表项是自绘控件，无 InvokePattern）。"""
        try:
            import ctypes
            rect = ctrl.BoundingRectangle
            if not rect:
                return False
            x = rect.left + rect.width() // 2
            y = rect.top + rect.height() // 2
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # 左键按下
            time.sleep(0.02)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # 左键抬起
            return True
        except Exception as e:
            log.debug(f"点击会话项失败: {e}")
            return False

    def _scroll_session_list(self, direction: int = 1, notches: int = 3):
        """把鼠标移到会话列表上滚动。direction: 1=向下翻(看更早的), -1=向上翻。"""
        lst = self._find_session_list()
        if lst is None:
            return
        try:
            import ctypes
            r = lst.BoundingRectangle
            if not r:
                return
            ctypes.windll.user32.SetCursorPos(int(r.left + r.width() // 2),
                                              int(r.top + r.height() // 2))
            time.sleep(0.05)
            # dwData 正值 = 向上滚；向下翻需要负值
            delta = -120 * notches * direction
            for _ in range(abs(delta) // 120):
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, (120 if delta > 0 else -120), 0)
                time.sleep(0.04)
        except Exception as e:
            log.debug(f"滚动会话列表失败: {e}")

    def _switch_contact_by_list(self, contact: str, max_scrolls: int = 10) -> bool:
        """
        在左侧会话列表中按名字找到目标会话并点击它。

        比 Ctrl+F 搜索更可靠：不会因为「搜索结果第一项不是目标」而发错人。
        列表按最近活跃排序，目标通常就在前几项；找不到才向下滚动翻找。
        """
        if not self._ensure_window():
            return False
        self._activate()
        time.sleep(0.15)

        item, rank = self._find_session_item(contact)
        scrolls = 0
        while item is None and scrolls < max_scrolls:
            self._scroll_session_list(direction=1, notches=3)
            time.sleep(0.2)
            item, rank = self._find_session_item(contact)
            scrolls += 1

        if item is None:
            log.info(f"会话列表（含滚动 {scrolls} 次）未找到 '{contact}'")
            if scrolls:
                # 滚回顶部，别把列表停在底部
                self._scroll_session_list(direction=-1, notches=3 * min(scrolls, 12))
                time.sleep(0.15)
            return False

        title = self._session_title(item)
        for attempt in (1, 2):
            if not self._click_control_center(item):
                return False
            time.sleep(0.6)  # 等聊天窗口切换完成
            if self._is_chat_open(contact):
                log.info(f"已切到会话: {title}（列表匹配，等级 {rank}）")
                return True
            if attempt == 1:
                log.info(f"点击后标题仍为 '{self._current_chat_title()}'，重试一次")

        log.warning(f"点击会话 '{title}' 后标题仍不匹配"
                    f"（当前 '{self._current_chat_title()}'）")
        return False

    # ================================================================
    # 当前会话校验（读聊天区标题栏）
    # ================================================================

    def _find_title_bar(self):
        """定位聊天区标题栏（mmui::ChatTitleBar*）。"""
        if not self._ensure_window():
            return None
        if self._title_bar is not None:
            try:
                self._title_bar.GetChildren()
                return self._title_bar
            except Exception:
                self._title_bar = None

        found = []

        def walk(ctrl, depth=0):
            if depth > 26 or found:
                return
            try:
                for ch in ctrl.GetChildren():
                    try:
                        if (ch.ControlTypeName == "GroupControl"
                                and "ChatTitleBar" in (ch.ClassName or "")):
                            found.append(ch)
                            return
                    except Exception:
                        pass
                    walk(ch, depth + 1)
            except Exception:
                pass

        try:
            walk(self._window)
        except Exception:
            pass
        if found:
            self._title_bar = found[0]
            return self._title_bar
        return None

    def _current_chat_title(self) -> str:
        """读取当前打开的会话名（标题栏上的文字）。读不到返回 ''。"""
        tb = self._find_title_bar()
        if tb is None:
            return ""

        def find_text(ctrl, depth=0):
            if depth > 12:
                return ""
            try:
                for ch in ctrl.GetChildren():
                    try:
                        if ch.ControlTypeName == "TextControl" and (ch.Name or "").strip():
                            return ch.Name.strip()
                    except Exception:
                        pass
                    r = find_text(ch, depth + 1)
                    if r:
                        return r
            except Exception:
                pass
            return ""

        return find_text(tb)

    def _is_chat_open(self, contact: str) -> bool:
        """当前打开的会话是否就是 contact。"""
        cur = self._current_chat_title()
        if not cur:
            return False  # 读不到就不敢说「是」
        return self._normalize_contact(cur) == self._normalize_contact(contact)

    def _switch_to_contact(self, contact: str) -> bool:
        """
        按 config.SWITCH_METHOD 选择切换方式：

          auto   —— 先「列表点击」，失败再退回「Ctrl+F 搜索」（默认）
          list   —— 只用列表点击
          search —— 只用 Ctrl+F 搜索
        """
        try:
            import config as _cfg
            method = getattr(_cfg, "SWITCH_METHOD", "auto")
        except Exception:
            method = "auto"

        if method == "search":
            return self._switch_contact(contact)

        if self._switch_contact_by_list(contact):
            return True

        if method == "list":
            return False

        log.info(f"会话列表未命中，改用搜索方式切换 '{contact}'")
        return self._switch_contact(contact)

    def _switch_contact(self, contact: str) -> bool:
        """
        切换到指定联系人/群聊的聊天窗口。

        Ctrl+F 搜索 → 粘贴 → Enter
        """
        if not self._ensure_window():
            return False
        self._activate()

        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return False

        hwnd = self._hwnd()
        if not hwnd:
            log.warning("找不到微信主窗口句柄")
            return False

        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top

        WE_CHAT_TID = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
        CURRENT_TID = ctypes.windll.kernel32.GetCurrentThreadId()
        ctypes.windll.user32.AttachThreadInput(CURRENT_TID, WE_CHAT_TID, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.BringWindowToTop(hwnd)
        time.sleep(0.3)

        try:
            # Ctrl+F 打开搜索
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl
            ctypes.windll.user32.keybd_event(0x46, 0, 0, 0)   # F
            ctypes.windll.user32.keybd_event(0x46, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
            time.sleep(0.5)

            # 清空搜索框
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl
            ctypes.windll.user32.keybd_event(0x41, 0, 0, 0)   # A
            ctypes.windll.user32.keybd_event(0x41, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
            time.sleep(0.15)

            # 粘贴联系人/群名
            import pyperclip
            pyperclip.copy(contact)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl
            ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)   # V
            ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
            time.sleep(0.3)

            # Enter → 选中第一个结果
            ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
            time.sleep(0.8)

            log.info(f"已切到联系人: {contact}")
            return True
        finally:
            ctypes.windll.user32.AttachThreadInput(CURRENT_TID, WE_CHAT_TID, False)

    def _locate_input(self) -> bool:
        """
        定位聊天输入框和发送按钮

        在 Electron 中，聊天输入框是 EditControl (支持 ValuePattern)，
        位于窗口下半部分。
        """
        if not self._ensure_window():
            return False

        # 如果已有缓存且窗口没变，直接返回
        if self._input_control is not None:
            try:
                if self._is_search_box(self._input_control):
                    raise ValueError("缓存控件是搜索框")
                self._input_control.GetCurrentPattern()
                return True
            except Exception:
                self._input_control = None
                self._send_button = None

        auto = self._auto
        win_rect = self._window.BoundingRectangle
        win_center_y = win_rect.top + win_rect.height() / 2

        edits = []

        def walk(ctrl, depth=0):
            if depth > 26:  # 微信 4.x 的 ChatInputField 在第 18 层左右
                return
            try:
                for child in ctrl.GetChildren():
                    try:
                        cn = child.ControlTypeName
                        # 输入控件
                        if cn == "EditControl":
                            edits.append(child)
                        walk(child, depth + 1)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            walk(self._window)
        except Exception as e:
            log.debug(f"UIA 遍历异常: {e}")

        if not edits:
            log.warning("未找到输入控件，使用坐标后备方案（Qt 界面）")
            self._use_coord_fallback = True
            return True

        # ---- 第一优先：按类名精确识别聊天输入框（mmui::ChatInputField）----
        chat_inputs = [e for e in edits
                       if self.CHAT_INPUT_CLASS in (e.ClassName or "")
                       and e.BoundingRectangle]
        if chat_inputs:
            chat_inputs.sort(key=lambda e: e.BoundingRectangle.width() *
                             e.BoundingRectangle.height(), reverse=True)
            self._input_control = chat_inputs[0]
            r = self._input_control.BoundingRectangle
            log.info(f"聊天输入框: {r.width()}x{r.height()} "
                     f"(ClassName={self._input_control.ClassName})")
        else:
            # ---- 第二优先：下半部分、面积较大的 EditControl，但必须排除搜索框 ----
            candidates = [e for e in edits
                          if e.BoundingRectangle
                          and not self._is_search_box(e)
                          and e.BoundingRectangle.top >= win_center_y - 20
                          and e.BoundingRectangle.width() > 150]

            # 绝不再退化为「所有 EditControl」——那会把搜索框当成输入框
            if not candidates:
                log.error("未能定位聊天输入框（仅找到搜索框/其他 EditControl）。"
                          "为避免把消息发进搜索框，本次发送中止。"
                          f"当前 EditControl: {[(e.ClassName, e.Name) for e in edits]}")
                return False

            candidates.sort(key=lambda e: e.BoundingRectangle.width() *
                            e.BoundingRectangle.height(), reverse=True)

            for ctrl in candidates:
                rect = ctrl.BoundingRectangle
                if rect.width() * rect.height() < 200:
                    continue
                has_value = _pattern_available(ctrl, VALUE_PATTERN_PROP)
                log.debug(f"输入候选: '{name_of(ctrl)}' {rect.width()}x{rect.height()} "
                          f"V={has_value}")
                if has_value:
                    self._input_control = ctrl
                    log.info(f"聊天输入框: {rect.width()}x{rect.height()} "
                             f"(ValuePattern, ClassName={ctrl.ClassName})")
                    break

            if not self._input_control:
                self._input_control = candidates[0]
                log.warning("输入框无 ValuePattern，使用 SendKeys 后备方案")
                log.debug(f"后备输入控件: {self._input_control.ControlTypeName} "
                          f"'{name_of(self._input_control)}'")

        # 查找发送按钮
        # 注意：真实发送按钮是 mmui::XOutlineButton '发送'，位于控件树第 18 层、
        # 输入框下方那一栏。旧代码 depth 上限 8 且会匹配「无名按钮」，结果抓到
        # 左侧栏的图标 —— 点了没反应，消息发不出去。
        try:
            buttons = []

            def find_buttons(ctrl, depth=0):
                if depth > 28:
                    return
                try:
                    for child in ctrl.GetChildren():
                        try:
                            if child.ControlTypeName == "ButtonControl":
                                bn = (child.Name or "").strip()
                                r = child.BoundingRectangle
                                # 只认名字里带「发送 / Send」的按钮
                                if r and bn and ("发送" in bn or "send" in bn.lower()):
                                    buttons.append((child, r, bn))
                        except Exception:
                            pass
                        find_buttons(child, depth + 1)
                except Exception:
                    pass

            find_buttons(self._window)

            ir = self._input_control.BoundingRectangle if self._input_control else None
            if buttons and ir:
                # 发送按钮在输入框下方的工具栏里；排除「发送表情」等左侧的功能键
                near = [b for b in buttons
                        if b[1].left >= ir.left and b[1].top >= ir.top - 30]
                if near:
                    buttons = near

            if buttons:
                # 优先名字正好是「发送」的，其次最靠右的
                buttons.sort(key=lambda b: (b[2] != "发送", -b[1].left))
                self._send_button = buttons[0][0]
                log.info(f"已定位发送按钮: '{buttons[0][2]}' "
                         f"{buttons[0][1].width()}x{buttons[0][1].height()}")
            else:
                self._send_button = None
                log.info("未找到发送按钮，发送时用 Enter")
        except Exception:
            self._send_button = None

        return True

    # ================================================================
    # 发送方法
    # ================================================================

    def _input_value(self, ctrl) -> str:
        """读取输入框当前文本；读不到返回 ''。"""
        try:
            v = ctrl.GetValuePattern().Value
            return v if isinstance(v, str) else ""
        except Exception:
            return ""

    def _send_current(self, ctrl, verify: bool = True) -> bool:
        """
        把输入框里已有的内容发出去。

        依次尝试：发送按钮 → Enter → Ctrl+Enter。
        verify=True 时以「输入框是否清空」作为成功判据 —— 发送按钮在输入框为空
        时是禁用状态，点了不报错，光看返回值判断不出来。发图片时输入框里没有
        文本，判据失效，调用方传 verify=False。
        """
        def cleared() -> bool:
            time.sleep(0.45)
            return self._input_value(ctrl).strip() == ""

        # 1) 发送按钮
        if self._send_button is not None:
            try:
                if _pattern_available(self._send_button, INVOKE_PATTERN_PROP):
                    self._send_button.GetInvokePattern().Invoke()
                else:
                    self._send_button.Click()
                if not verify or cleared():
                    return True
                log.debug("发送按钮未生效，改用 Enter")
            except Exception as e:
                log.debug(f"点击发送按钮失败: {e}")

        # 2) Enter（微信默认 Enter 发送）
        try:
            ctrl.SetFocus()
            time.sleep(0.05)
        except Exception:
            pass
        try:
            self._auto.SendKeys("{Enter}")
            if not verify or cleared():
                return True
        except Exception as e:
            log.debug(f"Enter 发送失败: {e}")

        # 3) Ctrl+Enter（用户把 Enter 改成「换行」时）
        try:
            self._auto.SendKeys("{Ctrl}{Enter}")
            if not verify or cleared():
                return True
        except Exception as e:
            log.debug(f"Ctrl+Enter 发送失败: {e}")

        return False

    def send_text(self, contact: str, text: str) -> bool:
        """
        发送文本消息

        Args:
            contact: 联系人昵称/备注
            text: 消息内容
        """
        with self._lock:
            if not self._ready:
                log.error("UIA Sender 未就绪")
                return False

            if not self._ensure_window():
                return False

            # 安全检查：过滤 PIL 引用
            if "<PIL." in text or "PIL." in text:
                log.warning(f"跳过 PIL 引用消息: {text[:60]}")
                return False

            self._activate()

            # 切换到联系人（默认：先在左侧会话列表按名字点击，失败退回搜索）
            # 用「当前会话标题」实际校验，不再依赖缓存 —— 避免你手动切了窗口后消息发错人
            if self.search_enabled and contact:
                if not self._is_chat_open(contact):
                    if not self._switch_to_contact(contact):
                        log.warning(f"无法自动切换到 '{contact}'，尝试在当前窗口发送")
                self._last_contact = contact

            # 定位输入框
            if not self._locate_input():
                return False

            try:
                if self._use_coord_fallback:
                    # Qt 界面：点击输入框区域→剪贴板粘贴→Enter
                    import pyperclip
                    import ctypes
                    from ctypes import wintypes
                    hwnd = self._hwnd()
                    if hwnd:
                        rect = wintypes.RECT()
                        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        win_w = rect.right - rect.left
                        win_h = rect.bottom - rect.top
                        # 输入框大致在窗口底部居中偏左的位置
                        input_x = rect.left + int(win_w * 0.3)
                        input_y = rect.top + int(win_h * 0.92)
                        # 物理点击让输入框获得焦点（PostMessage 对 Qt 子控件无效）
                        ctypes.windll.user32.SetCursorPos(input_x, input_y)
                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # down
                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # up
                    time.sleep(0.3)
                    pyperclip.copy(text)
                    time.sleep(0.05)
                    self._auto.SendKeys('{Ctrl}v')
                    time.sleep(0.3)
                    self._auto.SendKeys('{Enter}')
                    log.info(f"[UIA✓] {contact}: {text[:50]}... (无鼠标模式)")
                    return True

                ctrl = self._input_control

                # 让输入框获得焦点（SendKeys 只发给焦点控件，否则会打进搜索框）
                try:
                    ctrl.SetFocus()
                    time.sleep(0.05)
                except Exception:
                    pass

                # 设置文本
                if set_value(ctrl, "") and set_value(ctrl, text):
                    log.debug("已用 ValuePattern 写入输入框")
                else:
                    # 没有 ValuePattern：先物理点击输入框确保焦点，再剪贴板粘贴
                    log.warning("ValuePattern 不可用，改用「点击输入框 + 剪贴板」方案")
                    self._click_input_center()
                    import pyperclip
                    pyperclip.copy(text)
                    time.sleep(0.08)
                    self._auto.SendKeys('{Ctrl}a')
                    time.sleep(0.05)
                    self._auto.SendKeys('{Ctrl}v')

                time.sleep(0.1)

                # 发送（并确认输入框已清空，否则视为未发出）
                if not self._send_current(ctrl):
                    log.error(f"[UIA✗] {contact}: 内容已填入输入框但未能发出"
                              f"（输入框仍为 {self._input_value(ctrl)[:40]!r}）")
                    return False

                log.info(f"[UIA✓] {contact}: {text[:50]}...")
                return True

            except Exception as e:
                log.error(f"[UIA✗] {contact}: {e}")
                return False

    def send_image(self, contact: str, image_path: str) -> bool:
        """
        通过剪贴板发送图片

        Args:
            contact: 联系人
            image_path: 图片文件路径
        """
        with self._lock:
            if not self._ready:
                return False
            if not os.path.isfile(image_path):
                log.error(f"图片不存在: {image_path}")
                return False

            try:
                if not self._ensure_window():
                    return False
                self._activate()

                if self.search_enabled and contact:
                    if not self._is_chat_open(contact):
                        self._switch_to_contact(contact)
                    self._last_contact = contact

                # 复制图片到剪贴板
                self._copy_image_to_clipboard(image_path)
                time.sleep(0.2)

                if not self._locate_input():
                    return False

                if self._use_coord_fallback:
                    import ctypes
                    from ctypes import wintypes
                    hwnd = self._hwnd()
                    if hwnd:
                        rect = wintypes.RECT()
                        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        input_x = rect.left + int((rect.right - rect.left) * 0.3)
                        input_y = rect.top + int((rect.bottom - rect.top) * 0.92)
                        ctypes.windll.user32.SetCursorPos(input_x, input_y)
                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                    time.sleep(0.3)
                    self._auto.SendKeys('{Ctrl}v')
                    time.sleep(0.5)
                    self._auto.SendKeys('{Enter}')
                    log.info(f"[UIA✓] 图片 → {contact}: {os.path.basename(image_path)} (无鼠标模式)")
                    return True

                # 先把焦点放回聊天输入框，再粘贴（否则会贴进搜索框）
                try:
                    self._input_control.SetFocus()
                    time.sleep(0.1)
                except Exception:
                    self._click_input_center()
                self._auto.SendKeys('{Ctrl}v')
                time.sleep(0.6)

                # 发图片时输入框里没有文本，清空判据失效，故 verify=False
                if not self._send_current(self._input_control, verify=False):
                    log.error(f"[UIA✗] 图片 → {contact}: 已粘贴但未能发出")
                    return False

                log.info(f"[UIA✓] 图片 → {contact}: {os.path.basename(image_path)}")
                return True

            except Exception as e:
                log.error(f"[UIA✗] 图片 → {contact}: {e}")
                return False

    def _copy_image_to_clipboard(self, path: str):
        """复制图片到剪贴板（通过 PowerShell，避免 PIL 对象被当作文本复制）"""
        abs_path = os.path.abspath(path)
        try:
            subprocess.run([
                "powershell", "-WindowStyle", "Hidden", "-Command",
                f"Add-Type -AssemblyName System.Windows.Forms;"
                f"$img = [System.Drawing.Image]::FromFile('{abs_path}');"
                f"[System.Windows.Forms.Clipboard]::SetImage($img);"
                f"$img.Dispose()"
            ], check=True, timeout=10)
            log.debug("PowerShell 已复制图片到剪贴板")
        except Exception as e:
            log.error(f"复制图片到剪贴板失败: {e}")
            raise

    # ================================================================
    # 诊断
    # ================================================================

    def diagnose(self):
        """输出诊断信息，用于调试"""
        if not self._window:
            print("✗ 未找到微信窗口")
            return

        print(f"✓ 微信窗口: '{self._window.Name}'")
        print(f"  ClassName: {self._window.ClassName}")
        print(f"  Electron: {self._is_electron}")
        print(f"  位置: [{self._window.BoundingRectangle.left},"
              f"{self._window.BoundingRectangle.top}] "
              f"{self._window.BoundingRectangle.width()}x"
              f"{self._window.BoundingRectangle.height()}")

        print("\n--- UIA 树 ---")
        self._dump_tree(self._window, max_depth=4)

        print("\n--- 控件状态 ---")
        print(f"  输入框: {'✓' if self._input_control else '✗'}")
        print(f"  发送按钮: {'✓' if self._send_button else '✗'}")
