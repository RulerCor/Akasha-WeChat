# -*- coding: utf-8 -*-
"""开关文字错位 bug 的复现 + 修复验证。

问题（2026-09-15 用户反馈）：
  面板里点击开关后，开关的滑块内部会多出一个「开/关」字，叠在圆点上、被圆点遮住一半。
根因：
  onchange 用了 querySelector('span:last-child')，它会先命中 .switch 内部的滑块
  <span class="sl">（.switch 的最后一个子元素），于是文字被写进了滑块里。

本脚本用面板里真实的 <style> 生成一个最小页面，把「旧写法」和「新写法」并排渲染，
自动点击两个开关，然后交给 Edge 无头截图对比。旧写法会看到字叠进滑块，新写法不会。
"""
import io
import os
import re
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "bridge"))
import web_panel  # noqa: E402

OUT = r"C:/Users/Junqin Zhao/Documents/_shots"

style = re.search(r"<style>(.*?)</style>", web_panel.PAGE, re.S).group(1)

# 旧写法（有 bug）——原样复刻
OLD_ONCHANGE = (
    "this.closest('.switch-row').querySelector('span:last-child')"
    ".textContent=this.checked?'开':'关'"
)
# 新写法
NEW_ONCHANGE = "syncSwitchText(this)"

HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>%s
body{font-family:"Microsoft YaHei",sans-serif;padding:26px;width:430px;background:#fff}
.case{border:1px dashed #e6c9d3;border-radius:12px;padding:14px 16px;margin-bottom:16px}
.case h4{margin:0 0 10px;font-size:13px;color:#d6336e}
.case .tip{font-size:11.5px;color:#9a8790;margin-top:8px;line-height:1.6}
.bad{color:#c62828}.good{color:#2e7d32}
</style></head><body>

<div class="case">
  <h4>① 旧写法 span:last-child（复现 bug）</h4>
  <div class="settings-field wide"><label>把 @ 转成文字</label>
    <label class="switch-row"><span class="switch">
      <input type="checkbox" checked onchange="%s">
      <span class="sl"></span></span><span>开</span></label></div>
  <div class="tip bad">点击后：「关」字跑到滑块里面去了，被白色圆点遮住一半；右边的字还停在「开」。</div>
</div>

<div class="case">
  <h4>② 新写法 .st（已修复）</h4>
  <div class="settings-field wide"><label>把 @ 转成文字</label>
    <label class="switch-row"><span class="switch">
      <input type="checkbox" checked onchange="%s">
      <span class="sl"></span></span><span class="st">开</span></label></div>
  <div class="tip good">点击后：滑块干净无字，右边的文字正确变成「关」。</div>
</div>

<script>
function syncSwitchText(cb) {
  var row = cb.closest('.switch-row');
  var t = row && row.querySelector('.st');
  if (t) t.textContent = cb.checked ? '开' : '关';
}
// 打开页面即模拟用户「点一下」（开 -> 关）
window.addEventListener('load', function () {
  document.querySelectorAll('.switch input').forEach(function (cb) { cb.click(); });
});
</script>
</body></html>""" % (style, OLD_ONCHANGE, NEW_ONCHANGE)


def main():
    os.makedirs(OUT, exist_ok=True)
    page = os.path.join(OUT, "switch_verify.html")
    io.open(page, "w", encoding="utf-8", newline="\n").write(HTML)
    print("已生成:", page)

    edge = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    shot = os.path.join(OUT, "switch_verify.png")
    subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--virtual-time-budget=4000", "--window-size=480,620",
         "--screenshot=" + shot, "file:///" + page.replace("\\", "/")],
        capture_output=True,
    )
    print("已截图:", shot, "| 存在:", os.path.exists(shot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
