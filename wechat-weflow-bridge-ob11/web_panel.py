"""
Web 控制面板模块。

提供可视化控制页面（http://127.0.0.1:WEB_PORT），
支持启停/暂停/恢复桥接，显示运行状态和日志，
以及在线编辑 config.json 配置。
"""

import json
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

import state
import config

log = logging.getLogger("ob11-bridge")


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Akasha 奈奈山</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='28' font-size='28'>💎</text></svg>">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Segoe UI',sans-serif;background:linear-gradient(135deg,#fdf2f5,#fce4ec,#f8e8f0);height:100vh;color:#4a4a4a;display:flex;margin:0;overflow:hidden}

/* ===== 主容器 ===== */
.container{display:flex;width:100vw;height:100vh;background:rgba(255,255,255,0.75);backdrop-filter:blur(20px);overflow:hidden;border:none}

/* ===== 侧边栏 ===== */
.sidebar{width:132px;min-width:132px;background:linear-gradient(180deg,#fce4ec,#f8e8f0);display:flex;flex-direction:column;align-items:center;padding:24px 0;gap:4px;border-right:1px solid rgba(240,98,146,0.1);height:100vh}
.sidebar .logo{font-size:18px;font-weight:800;color:#d6336e;margin-bottom:22px;letter-spacing:3px;text-shadow:0 1px 3px rgba(214,51,110,0.15);font-family:'Quicksand','Segoe UI',sans-serif}
.sidebar .nav-item{width:110px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .25s;color:#b06c7a;font-size:13px;font-weight:600;gap:7px;border:none;background:transparent;padding:0 10px}
.sidebar .nav-item .icon{font-size:18px;line-height:1}
.sidebar .nav-item:hover{background:rgba(240,98,146,0.08);color:#d4567a}
.sidebar .nav-item.active{background:linear-gradient(135deg,#f48fb1,#f06292);color:#fff;box-shadow:0 4px 12px rgba(240,98,146,0.25)}
.sidebar .nav-item.active:hover{color:#fff}
.sidebar .side-foot{margin-top:auto;font-size:10.5px;color:#c9a3ad;line-height:1.6;text-align:center;padding:0 8px}

/* ===== 内容区 ===== */
.content{flex:1;padding:24px 30px 0;overflow-y:auto;display:flex;flex-direction:column;gap:16px;height:100vh}
.content::-webkit-scrollbar{width:5px}
.content::-webkit-scrollbar-thumb{background:#f0ced9;border-radius:4px}

.tab-page{display:none;flex-direction:column;gap:16px;height:100%}
.tab-page.active{display:flex}

/* ===== 头部 ===== */
.header{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.header h1{font-size:24px;font-weight:800;color:#c2185b;letter-spacing:.5px}
.header h1 .en{font-family:'Quicksand','Segoe UI',sans-serif;margin-right:8px}
.header h1 .cn{font-size:17px;color:#ad6478;font-weight:700}
.header .sub{font-size:12.5px;color:#b08a92}
.badge{background:#fce4ec;color:#ad6478;border-radius:999px;padding:4px 12px;font-size:11.5px;font-weight:600}
.badge.ok{background:#e8f5e9;color:#2e7d32}
.badge.warn{background:#fff3e0;color:#e65100}

/* ===== 卡片 ===== */
.card{background:#fff;border-radius:16px;padding:16px 20px;box-shadow:0 2px 10px rgba(214,51,110,0.06);border:1px solid #f9e6ec}
.card>h3{font-size:14.5px;color:#c2185b;margin-bottom:4px;display:flex;align-items:center;gap:7px}
.card>h3 .ic{font-size:16px}
.card>.card-sub{font-size:12px;color:#a97f88;line-height:1.6;margin-bottom:10px}

/* ===== 面板页 ===== */
.status-row{display:flex;gap:12px;flex-wrap:wrap}
.status-card{flex:1;min-width:130px;background:#fff;border-radius:14px;padding:12px 16px;box-shadow:0 2px 8px rgba(214,51,110,0.05);border:1px solid #f9e6ec}
.status-card .label{font-size:11px;color:#b08a92;margin-bottom:3px}
.status-card .value{font-size:16px;font-weight:700;color:#c2185b}
.btn-row{display:flex;gap:10px;flex-wrap:wrap}
.mode-row{display:flex;align-items:center;gap:10px;background:#fff;border-radius:12px;padding:10px 16px;border:1px solid #f9e6ec;font-size:13px;color:#7a5a62}
.mode-value{font-weight:700;color:#c2185b}
.log-box{flex:1;min-height:200px;background:#2d2226;color:#e8d5da;border-radius:14px;padding:14px;font-family:Consolas,monospace;font-size:11.5px;line-height:1.55;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.log-box::-webkit-scrollbar{width:5px}
.log-box::-webkit-scrollbar-thumb{background:#5a4a50;border-radius:4px}

/* ===== 按钮 ===== */
.btn{border:none;border-radius:11px;padding:9px 20px;font-size:13px;font-weight:700;cursor:pointer;transition:all .2s;color:#fff;box-shadow:0 2px 6px rgba(0,0,0,0.06)}
.btn:disabled{opacity:.45;cursor:not-allowed;box-shadow:none}
.btn-pink{background:linear-gradient(135deg,#f48fb1,#ec407a)}
.btn-pink:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 4px 12px rgba(236,64,122,0.3)}
.btn-red{background:linear-gradient(135deg,#ef5350,#e53935)}
.btn-amber{background:linear-gradient(135deg,#ffb74d,#ffa726)}
.btn-green{background:linear-gradient(135deg,#66bb6a,#43a047)}
.btn-outline{background:#fff;color:#d4567a;border:1.5px solid #f0b9c8}
.btn-outline:hover{background:#fdf2f5}
.btn-sm{padding:5px 12px;font-size:12px;border-radius:9px}

/* ===== 设置表单 ===== */
.settings-scroll{flex:1;display:flex;flex-direction:column;gap:14px;overflow-y:auto;padding-bottom:8px;min-height:0}
.settings-scroll::-webkit-scrollbar{width:5px}
.settings-scroll::-webkit-scrollbar-thumb{background:#f0ced9;border-radius:4px}

.set-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#fff;border-radius:14px;padding:10px 16px;border:1px solid #f9e6ec;position:sticky;top:0;z-index:5;box-shadow:0 2px 10px rgba(214,51,110,0.07)}
.set-bar .search-input{flex:1;min-width:180px}
.set-note{font-size:11.5px;color:#b08a92}

.settings-row{display:flex;flex-wrap:wrap;gap:12px 18px}
.settings-field{flex:1;min-width:230px;display:flex;flex-direction:column;gap:5px}
.settings-field.wide{flex-basis:100%}
.settings-field label{font-size:12px;color:#8a6a72;font-weight:600;line-height:1.5}
.settings-field input,.settings-field select,.settings-field textarea{padding:8px 11px;border:1.5px solid #f0e2e6;border-radius:10px;font-size:12.5px;outline:none;background:#fffdfa;color:#4a4a4a;font-family:inherit;transition:border-color .2s}
.settings-field input:focus,.settings-field select:focus,.settings-field textarea:focus{border-color:#f06292}
.settings-field textarea{resize:vertical}
.restart-badge{display:inline-block;font-size:10px;background:#fff3e0;color:#e65100;border-radius:6px;padding:1px 6px;margin-left:5px;font-weight:600;vertical-align:1px}
.new-badge{display:inline-block;font-size:10px;background:#e3f2fd;color:#1565c0;border-radius:6px;padding:1px 6px;margin-left:5px;font-weight:600;vertical-align:1px}
.field-hint{font-size:11px;color:#b9a0a7;line-height:1.6}

/* 折叠层 */
details.tier{background:#fff;border-radius:16px;border:1px solid #f9e6ec;box-shadow:0 2px 10px rgba(214,51,110,0.05);overflow:hidden}
details.tier>summary{list-style:none;cursor:pointer;padding:13px 20px;font-size:13.5px;font-weight:700;color:#ad6478;display:flex;align-items:center;gap:8px;user-select:none}
details.tier>summary::-webkit-details-marker{display:none}
details.tier>summary .arrow{transition:transform .2s;font-size:11px;color:#d8aeb8}
details.tier[open]>summary .arrow{transform:rotate(90deg)}
details.tier>summary .count{font-size:11px;color:#c9a3ad;font-weight:600}
details.tier>.tier-body{padding:2px 20px 16px;display:flex;flex-direction:column;gap:14px}
details.tier.warn{border-color:#ffe0b2}
details.tier.warn>summary{color:#e65100}
details.tier.warn>.tier-body{background:linear-gradient(180deg,#fffdf8,#fff);margin-top:0}

/* 信息提示 */
.hint-text{font-size:12px;color:#8a6a72;line-height:1.75;background:#fdf7f9;border-radius:12px;padding:10px 14px;border:1px solid #faeef2}
.hint-text b{color:#d4567a}
.hint-text.amber{background:#fffaf2;border-color:#ffedd0}
.hint-text.amber b{color:#e65100}
.info-line{flex-basis:100%;max-width:100%;font-size:12.5px;line-height:1.7;color:#8a6a72;background:#f7fbff;border:1px solid #e3f0fb;border-radius:12px;padding:10px 14px}

/* 开关 */
.switch{position:relative;display:inline-block;width:38px;height:21px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch .sl{position:absolute;inset:0;background:#e8d5da;border-radius:999px;transition:.25s;cursor:pointer}
.switch .sl:before{content:"";position:absolute;height:15px;width:15px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.25s;box-shadow:0 1px 3px rgba(0,0,0,.15)}
.switch input:checked+.sl{background:linear-gradient(135deg,#f48fb1,#ec407a)}
.switch input:checked+.sl:before{transform:translateX(17px)}
.switch-row{display:flex;align-items:center;gap:10px;font-size:12.5px;color:#5a4a50;cursor:pointer}

/* 保存条 */
.save-bar{position:sticky;bottom:0;background:rgba(255,255,255,0.92);backdrop-filter:blur(8px);border-radius:14px;padding:10px 16px;display:flex;align-items:center;gap:12px;border:1px solid #f9e6ec;box-shadow:0 -2px 14px rgba(214,51,110,0.08);z-index:5;margin-bottom:14px}
.save-bar .spacer{flex:1}
.save-msg{font-size:12px;color:#2e7d32;font-weight:600;opacity:0;transition:opacity .25s}
.save-msg.show{opacity:1}

/* ===== 表格 ===== */
.member-table{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #f5e4e8}
.member-table th{background:#fce4ec;color:#ad6478;text-align:left;padding:8px 10px;font-weight:600;font-size:11.5px;white-space:nowrap}
.member-table td{padding:7px 10px;border-top:1px solid #f8eef1;color:#5a4a50;word-break:break-all;vertical-align:middle}
.member-table tr:hover td{background:#fdf7f9}
.member-table .wxid{color:#b09098;font-size:11px}
.member-table .uid{color:#8a7a80;font-size:11px;font-family:monospace}
.member-table .gname{font-weight:600;color:#6a4a52}
.member-table .center{text-align:center}
.tbl-scroll{max-height:380px;overflow-y:auto;border-radius:12px;border:1px solid #f5e4e8}
.tbl-scroll .member-table{border:none;border-radius:0}
.tbl-scroll::-webkit-scrollbar{width:5px}
.tbl-scroll::-webkit-scrollbar-thumb{background:#f0ced9;border-radius:4px}
.tbl-scroll thead th{position:sticky;top:0;z-index:2}
.admin-badge{display:inline-block;font-size:10px;background:linear-gradient(135deg,#f48fb1,#ec407a);color:#fff;border-radius:6px;padding:1px 6px;margin-left:6px;font-weight:600}
.copy-chip{display:inline-block;background:#fdf2f5;border:1px solid #f7dce4;color:#ad6478;border-radius:8px;padding:2px 8px;font-size:11px;font-family:monospace;cursor:pointer;transition:all .15s;white-space:nowrap}
.copy-chip:hover{background:#f8e3ea;color:#c2185b}
.search-input{padding:7px 12px;border:1.5px solid #f0e2e6;border-radius:10px;font-size:12px;outline:none;background:#fff;transition:border-color .2s}
.search-input:focus{border-color:#f06292}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.toolbar .spacer{flex:1}

/* 群勾选 chip（高级区用） */
.chip-wrap{display:flex;flex-wrap:wrap;gap:8px 10px;padding:4px 0}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:#6a4a52;background:#fdf5f7;border:1.5px solid #f7e3e9;border-radius:999px;padding:4px 11px;cursor:pointer;transition:all .18s;user-select:none}
.chip:hover{border-color:#f0a8bd}
.chip.on{background:linear-gradient(135deg,#fde3ec,#fcd5e3);border-color:#f08cad;color:#c2185b;font-weight:600}
.chip input{display:none}
.chip .dot{width:7px;height:7px;border-radius:50%;background:#e3c4cd;transition:.18s}
.chip.on .dot{background:#ec407a}
</style>
</head>
<body>

<div class="toast" id="toast"></div>

<div class="container">

<!-- ===== 侧边栏 ===== -->
<div class="sidebar">
  <div class="logo">Akasha</div>
  <button class="nav-item active" data-tab="dashboard" onclick="switchTab('dashboard')">
    <span class="icon">🏠</span><span>控制面板</span>
  </button>
  <button class="nav-item" data-tab="settings" onclick="switchTab('settings')">
    <span class="icon">⚙️</span><span>基础设置</span>
  </button>
  <button class="nav-item" data-tab="members" onclick="switchTab('members')">
    <span class="icon">👥</span><span>成员与权限</span>
  </button>
  <div class="side-foot">微信 ↔ AstrBot<br>桥接面板</div>
</div>

<!-- ===== 内容区 ===== -->
<div class="content">

  <!-- ===== 面板页 ===== -->
  <div class="tab-page active" id="page-dashboard">
    <div class="header">
      <h1><span class="en">Akasha</span><span class="cn">奈奈山</span></h1>
      <div class="badge" id="statusText">加载中...</div>
    </div>

    <div class="status-row">
      <div class="status-card"><div class="label">桥接状态</div><div class="value" id="bridgeStatus">-</div></div>
      <div class="status-card"><div class="label">AstrBot</div><div class="value" id="obStatus">-</div></div>
      <div class="status-card"><div class="label">WeFlow</div><div class="value" id="weflowStatus">-</div></div>
      <div class="status-card"><div class="label">发送模式</div><div class="value" id="sendMethod" style="font-size:13px">-</div></div>
    </div>

    <div class="btn-row">
      <button class="btn btn-pink" id="btnStart" onclick="action('start')">▶ 启动</button>
      <button class="btn btn-red" id="btnStop" onclick="action('stop')" disabled>■ 停止</button>
      <button class="btn btn-amber" id="btnPause" onclick="action('pause')" disabled>⏸ 暂停</button>
      <button class="btn btn-green" id="btnResume" onclick="action('resume')" style="display:none" disabled>▶ 恢复</button>
    </div>

    <div class="mode-row">
      <span>群聊模式:</span>
      <span class="mode-value" id="modeStatus">-</span>
      <button class="btn btn-outline btn-sm" id="btnToggleMode">切换</button>
      <span style="font-size:11.5px;color:#b9a0a7">标准 = @必回、非@由 AstrBot 掷骰决定 ｜ 批处理 = 整群消息合并成一条再处理</span>
    </div>

    <div class="log-box" id="log">等待连接...</div>
  </div>

  <!-- ===== 设置页 ===== -->
  <div class="tab-page" id="page-settings">
    <div class="header">
      <h1><span class="en">Settings</span><span class="cn">基础设置</span></h1>
      <div class="badge">config.json</div>
      <span class="sub">改完记得重启桥接才生效（群聊模式除外，立即生效）</span>
    </div>

    <div class="set-bar">
      <input class="search-input" id="cfgSearch" placeholder="🔍 搜设置项，比如：图片 / 昵称 / 端口 / Token" oninput="filterSettings()">
      <span class="set-note" id="cfgSearchCount"></span>
    </div>

    <div class="settings-scroll" id="settingsForm">
      <!-- 由 JS 动态渲染 -->
    </div>

    <div class="save-bar">
      <span class="save-msg" id="saveMsg">✅ 已保存</span>
      <span class="set-note">💾 保存后<b style="color:#e65100">重启桥接</b>生效；群聊模式改动立即生效</span>
      <div class="spacer"></div>
      <button class="btn btn-pink" onclick="saveConfig()">💾 保存配置</button>
    </div>
  </div>

  <!-- ===== 成员与权限页 ===== -->
  <div class="tab-page" id="page-members">
    <div class="header">
      <h1><span class="en">People</span><span class="cn">成员与权限</span></h1>
      <div class="badge" id="membersBadge">加载中...</div>
    </div>

    <div class="settings-scroll">

      <div class="hint-text">
        这里管三件事：<b>👑 谁是管理员</b>（能指挥机器人做跨群操作）｜
        <b>💬 机器人在哪些群说话、会不会自己插嘴</b>（下面一张表全搞定）｜
        <b>🔧 更细的白名单</b>（折叠在「高级」里，一般用不到）。
      </div>

      <!-- 👑 管理员 -->
      <div class="card">
        <h3><span class="ic">👑</span>管理员</h3>
        <div class="card-sub">管理员可以使用跨群发消息等敏感能力。<b>同一个人在私聊和所有群里算同一个 ID</b>，勾一次全局生效，不用逐群加。</div>
        <div class="toolbar" style="margin-bottom:8px">
          <input class="search-input" id="memberSearch" placeholder="🔍 搜名字 / wxid" oninput="renderPeople()">
          <div class="spacer"></div>
          <button class="btn btn-pink btn-sm" onclick="saveAdmins()">💾 保存管理员</button>
        </div>
        <div class="tbl-scroll">
        <table class="member-table">
          <thead><tr><th style="width:44px" class="center">管理</th><th>昵称</th><th style="width:190px">wxid</th><th>UID（/sid 显示的 ID）</th></tr></thead>
          <tbody id="peopleBody"><tr><td colspan="4" style="color:#c0aab0">加载中...</td></tr></tbody>
        </table>
        </div>
        <div class="field-hint" style="margin-top:6px">共 <span id="peopleCount">-</span> 人，表格内可直接滚动；搜索框在上面。</div>
      </div>

      <!-- 💬 群行为总表 -->
      <div class="card">
        <h3><span class="ic">💬</span>群里管什么<span class="new-badge">一张表全搞定</span></h3>
        <div class="card-sub">
          <b>回复</b> = 收到消息后要不要理这个群（关掉就是完全不掺和，@ 也不理，立即生效）。<br>
          <b>插嘴</b> = 没 @ 它的时候，会不会自己冒出来说话（走下面的全局开关 + 概率）。@ 它永远会回，跟这两列都无关。
        </div>
        <div id="arWhitelistWarn" style="display:none;margin-bottom:8px"></div>
        <table class="member-table">
          <thead><tr>
            <th style="width:52px" class="center">回复</th>
            <th style="width:52px" class="center">插嘴</th>
            <th>群名</th>
            <th style="width:120px">群 ID</th>
            <th>UMO（完整会话标识，点一下复制）</th>
          </tr></thead>
          <tbody id="groupsBody"><tr><td colspan="5" style="color:#c0aab0">加载中...</td></tr></tbody>
        </table>
        <div class="field-hint" style="margin-top:7px">「插嘴」这列改完要和下面的全局设置一起<b>点保存</b>才生效。</div>
      </div>

      <!-- 🎲 全局插话 -->
      <div class="card">
        <h3><span class="ic">🎲</span>随机插话（全局）</h3>
        <div class="card-sub">就是 AstrBot 里的「主动回复」：群消息<b>不是 @ 机器人</b>时，按概率掷骰决定要不要插一嘴。关掉 = 它只在你 @ 它的时候说话。</div>
        <div class="settings-row">
          <div class="settings-field" style="min-width:150px;max-width:190px">
            <label>随机插话总开关</label>
            <select id="ab_ar_enable"><option value="0">关闭</option><option value="1">开启</option></select>
          </div>
          <div class="settings-field" style="min-width:150px;max-width:220px">
            <label>插话概率（0~1，每条群消息掷一次）</label>
            <input type="number" id="ab_ar_poss" step="0.01" min="0" max="1" placeholder="0.03">
            <span class="field-hint">建议 0.02~0.05，太高会刷屏</span>
          </div>
          <div class="settings-field" style="min-width:220px">
            <label>生效前提</label>
            <span class="field-hint" style="margin-top:4px">① 桥接群聊模式为<b>标准</b>（批处理不转发非@消息）；② 该群先用 /new 建立过会话；③ 保存后需重启 AstrBot。</span>
          </div>
        </div>
      </div>

      <!-- 🔧 高级 -->
      <details class="tier" id="tierAdvanced">
        <summary><span class="arrow">▶</span>🔧 高级：手动填 ID / 白名单<span class="count">一般用不到</span></summary>
        <div class="tier-body">
          <div class="hint-text amber">
            <b>这三层过滤的关系</b>（从粗到细，命中即生效）：<br>
            ① <b>平台 ID 白名单</b>——总闸。开了之后，不在名单里的会话<b>整条消息都不进 AstrBot</b>（连 @ 都不理）。<br>
            ② <b>群回复开关</b>——桥接侧开关，上面那张表的「回复」列，关了就是完全不理。<br>
            ③ <b>插话白/黑名单</b>——只影响「没人 @ 时要不要插嘴」；<b>黑名单优先于白名单</b>；白名单留空 = 所有群都可能插嘴。<br>
            想手写条目的话，填<b>群 ID</b> 或完整 <b>UMO</b> 都行（UMO 在上面那张表里点一下就能复制）。
          </div>
          <div class="settings-row">
            <div class="settings-field" style="min-width:150px;max-width:190px">
              <label>平台 ID 白名单开关</label>
              <select id="ab_wl_enable"><option value="0">关闭（不过滤）</option><option value="1">开启</option></select>
            </div>
            <div class="settings-field wide">
              <label>平台 ID 白名单（点选群）</label>
              <div id="ab_wl_groups" class="chip-wrap"></div>
            </div>
            <div class="settings-field wide">
              <label>平台白名单 · 手动补充（群 ID / UMO，逗号或换行分隔）</label>
              <textarea id="ab_wl_extra" rows="2" placeholder="留空即可"></textarea>
            </div>
          </div>
          <div class="settings-row">
            <div class="settings-field wide">
              <label>插话白名单（只在这些群插嘴；留空 = 所有群；点选群）</label>
              <div id="ab_ar_groups" class="chip-wrap"></div>
            </div>
            <div class="settings-field wide">
              <label>插话白名单 · 手动补充（群 ID / UMO，逗号或换行分隔）</label>
              <textarea id="ab_ar_extra" rows="2" placeholder="留空即可"></textarea>
            </div>
            <div class="settings-field wide">
              <label>插话黑名单 · 手动补充（上面表格没勾「插嘴」的群会自动进这里；此处只放列表里没有的群 ID / UMO）</label>
              <textarea id="ab_ar_black_extra" rows="2" placeholder="留空即可"></textarea>
            </div>
          </div>
        </div>
      </details>

    </div>

    <div class="save-bar">
      <span class="save-msg" id="abMsg">✅ 已写入 AstrBot 配置</span>
      <span class="set-note">管理员立即生效；白名单 / 插话设置需<b style="color:#e65100">重启 AstrBot</b></span>
      <div class="spacer"></div>
      <button class="btn btn-pink" onclick="saveAstrbotCfg()">💾 保存到 AstrBot</button>
    </div>
  </div>

</div>
</div>

<script>
// ===== 工具 =====
function toast(msg, type) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type + ' show';
  setTimeout(function(){t.className='toast'}, 2500);
}

function showMsg(id, text) {
  var el = document.getElementById(id);
  el.textContent = text;
  el.className = 'save-msg show';
  setTimeout(function(){el.className='save-msg'}, 3000);
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ===== Tab 切换 =====
function switchTab(name) {
  document.querySelectorAll('.tab-page').forEach(function(p){p.classList.remove('active')});
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});
  document.querySelector('[data-tab="' + name + '"]').classList.add('active');
  if (name === 'settings') loadConfig();
  if (name === 'members') switchTabMembers();
}

// ===== 面板刷新 =====
var modeMap = {'mention':'标准模式','all':'标准模式','batch':'批处理'};

function refreshDashboard() {
  fetch('/status').then(function(r){return r.json()}).then(function(s){
    var st = document.getElementById('bridgeStatus');
    if (!s.running) { st.textContent='未运行'; st.style.color='#bdbdbd';
    } else if (s.paused) { st.textContent='已暂停'; st.style.color='#ff9800';
    } else { st.textContent='运行中'; st.style.color='#4caf50'; }

    document.getElementById('statusText').textContent = s.running ? (s.paused ? '已暂停' : '运行中') : '未运行';
    document.getElementById('obStatus').textContent = s.ob_connected ? '已连接' : '未连接';
    document.getElementById('obStatus').style.color = s.ob_connected ? '#4caf50' : '#bdbdbd';
    document.getElementById('weflowStatus').textContent = s.weflow_connected ? '已连接' : '未连接';
    document.getElementById('weflowStatus').style.color = s.weflow_connected ? '#4caf50' : '#bdbdbd';
    document.getElementById('sendMethod').textContent = s.send_method;

    document.getElementById('btnStart').disabled = s.running;
    document.getElementById('btnStop').disabled = !s.running;
    if (s.paused) {
      document.getElementById('btnPause').style.display = 'none';
      document.getElementById('btnResume').style.display = 'inline-block';
      document.getElementById('btnResume').disabled = false;
    } else {
      document.getElementById('btnPause').style.display = 'inline-block';
      document.getElementById('btnPause').disabled = !s.running;
      document.getElementById('btnResume').style.display = 'none';
    }

    document.getElementById('modeStatus').textContent = modeMap[s.group_reply_mode] || s.group_reply_mode;

    var logEl = document.getElementById('log');
    var isAtBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 40;
    logEl.textContent = s.log || '';
    if (isAtBottom) logEl.scrollTop = logEl.scrollHeight;
  });
}

function action(cmd) {
  fetch('/' + cmd, {method:'POST'}).then(function(){setTimeout(refreshDashboard,500)});
}

document.getElementById('btnToggleMode').onclick = function(){
  fetch('/mode', {method:'POST'}).then(function(){setTimeout(refreshDashboard,500)});
};

// ===== 设置定义 =====
// tier: common=常驻展示  adv=折叠（进阶）  legacy=折叠（上游遗留，一般别动）
var CFG_GROUPS = [
  {tier:'common', icon:'🐱', title:'机器人身份', sub:'它在微信里叫什么、被什么名字唤醒', fields:[
    {key:'bot_nicknames', label:'机器人昵称（逗号分隔，@ 其中任何一个都会唤醒）', type:'text', ph:'Mon3tr, M3, 小猫'},
    {key:'bot_wxid', label:'机器人自己的 wxid', type:'text', ph:'wxid_xxx', restart:1},
  ]},
  {tier:'common', icon:'💬', title:'消息行为', sub:'它怎么读群消息、怎么回话', fields:[
    {key:'buffer_seconds', label:'消息缓冲（秒）：同一个人连发多条时，等这么久再合并成一条', type:'number', ph:'5'},
    {key:'group_reply_mode', label:'群聊模式（控制台也能一键切换，此项立即生效）', type:'select', opts:[
      {v:'all',l:'标准模式（@必回；非@消息交给 AstrBot 掷骰决定）'},
      {v:'batch',l:'批处理（一段时间内整群消息合并成一条）'}]},
    {key:'mention_as_text', label:'把 @ 转成文字「@昵称」（微信原生 @ 发不出去时的替代方案）', type:'toggle', def:'true'},
    {key:'quote_reply_prefix', label:'引用回复转文字前缀（把「回复某条消息」变成〔回复 某某：原文〕）', type:'toggle', def:'false'},
    {key:'quote_reply_native', label:'原生引用气泡（当前微信 4.x 的右键菜单对 UIA 不可见，实测不可用，保持关闭）', type:'toggle', def:'false'},
  ]},
  {tier:'common', icon:'🖼️', title:'图片', sub:'群里发图怎么处理', fields:[
    {key:'image_mention_window', label:'群图片等待 @ 的时间窗（秒）：图先到，同一人在窗口内 @ 才会读图', type:'number', ph:'120'},
    {key:'image_max_bytes', label:'单张图片大小上限（字节），超过就跳过', type:'number', ph:'8388608'},
    {type:'info', text:'<b>「怎么理解图片」不在这里配</b>：图片默认原样转交 AstrBot，由 AstrBot 面板(6185) → 配置 里的主模型（多模态）或图片转述模型决定。下面「上游遗留」里的桥接侧转述是备用方案，默认关闭。'},
  ]},
  {tier:'adv', icon:'🔌', title:'连接', sub:'本机服务地址，一般不动', fields:[
    {key:'weflow_base_url', label:'WeFlow 地址', type:'text', ph:'http://127.0.0.1:5031'},
    {key:'access_token', label:'WeFlow Access Token', type:'password', ph:'输入 Token'},
    {key:'astrbot_ob_url', label:'AstrBot OneBot 反向 WS 地址', type:'text', ph:'ws://127.0.0.1:11229/ws', restart:1},
    {key:'astrbot_attachments', label:'附件目录（AstrBot 存图片的路径）', type:'text', ph:'C:\\astrbot\\attachments'},
    {key:'astrbot_config_file', label:'AstrBot 主配置路径（成员与权限页同步用）', type:'text', ph:'留空 = 自动探测 ../AstrBot/data/cmd_config.json', restart:1},
  ]},
  {tier:'adv', icon:'🧰', title:'面板与排障', sub:'面板端口、日志开关', fields:[
    {key:'web_port', label:'Web 面板端口', type:'number', ph:'8766', restart:1},
    {key:'web_host', label:'Web 面板监听地址', type:'text', ph:'0.0.0.0', restart:1},
    {key:'log_skipped_messages', label:'记录被跳过的消息（排障时强烈建议开着）', type:'toggle', def:'true'},
    {key:'switch_method', label:'联系人切换方式（UIA 发送时怎么找到聊天窗口）', type:'select', opts:[
      {v:'auto',l:'自动（先会话列表，找不到再搜索）'},
      {v:'list',l:'仅会话列表点击'},
      {v:'search',l:'仅 Ctrl+F 搜索'}]},
  ]},
  {tier:'legacy', icon:'📦', title:'上游遗留（默认关闭 · 一般不用动）', sub:'这些是上游 Akasha-WeChat 留下来的备用方案，当前链路用不到', fields:[
    {key:'send_method', label:'发送方式（<b>只有 UIA 能用</b>：WeFlow 没有发送接口，选它必然发不出去）', type:'select', opts:[
      {v:'uia',l:'UIA 自动化（微信 PC 客户端）——唯一可用'},
      {v:'weflow_api',l:'WeFlow API（实测不可用，勿选）'}]},
    {key:'weflow_send_api', label:'WeFlow 发送 API（<b>当前代码没有使用这个配置</b>，仅保留兼容）', type:'text', ph:'http://127.0.0.1:5031/api/v1/message'},
    {key:'image_caption_model', label:'桥接侧图片转述模型名（留空 = 不启用，走 AstrBot 配置）', type:'text', ph:'留空即可'},
    {key:'image_caption_provider', label:'转述服务', type:'select', opts:[{v:'ollama',l:'Ollama 本地'},{v:'openai',l:'OpenAI 兼容'}]},
    {key:'image_caption_api_key', label:'转述 API Key（OpenAI 模式）', type:'password', ph:'sk-xxx'},
    {key:'image_caption_api_base', label:'转述 API 地址（OpenAI 模式）', type:'text', ph:'https://api.moonshot.cn/v1'},
    {key:'image_caption_prompt', label:'转述提示词', type:'textarea', ph:'请用中文描述...'},
    {key:'ollama_base_url', label:'Ollama 地址', type:'text', ph:'http://127.0.0.1:61000'},
    {key:'ollama_timeout', label:'Ollama 超时（秒）', type:'number', ph:'60'},
  ]},
];

// ===== 设置加载 =====
function loadConfig() {
  fetch('/api/config').then(function(r){return r.json()}).then(function(cfg){
    renderConfigForm(cfg);
    filterSettings();
  }).catch(function(e){
    document.getElementById('settingsForm').innerHTML = '<p style="color:#e57373;font-size:13px;">加载配置失败: ' + e.message + '</p>';
  });
}

function renderConfigForm(cfg) {
  var TIER_META = {
    common: null,
    adv: {icon:'🔧', title:'进阶', note:'连接地址、端口、日志 —— 一般不用动'},
    legacy: {icon:'📦', title:'上游遗留', note:'默认关闭的备用方案，保持原样即可'},
  };
  var html = '';

  CFG_GROUPS.forEach(function(g){
    var meta = TIER_META[g.tier];
    var inner = '<div class="settings-row">';
    g.fields.forEach(function(f){ inner += renderField(f, cfg); });
    inner += '</div>';

    if (!meta) {
      html += '<div class="card" data-tier="common"><h3><span class="ic">' + g.icon + '</span>' + g.title + '</h3>'
        + '<div class="card-sub">' + g.sub + '</div>' + inner + '</div>';
    } else {
      html += '<details class="tier' + (g.tier === 'legacy' ? ' warn' : '') + '" data-tier="' + g.tier + '">'
        + '<summary><span class="arrow">▶</span>' + meta.icon + ' ' + g.title
        + ' <span class="count">' + meta.note + '</span></summary>'
        + '<div class="tier-body">' + inner + '</div></details>';
    }
  });

  document.getElementById('settingsForm').innerHTML = html;
}

function renderField(f, cfg) {
  if (f.type === 'info') {
    return '<div class="info-line">' + f.text + '</div>';
  }
  var val = cfg[f.key] !== undefined ? cfg[f.key] : (f.def !== undefined ? f.def : '');
  if (f.key === 'group_reply_mode' && val === 'mention') val = 'all'; // 旧值兼容
  if (typeof val === 'boolean') val = val ? 'true' : 'false';
  if (Array.isArray(val)) val = val.join(', ');

  var badge = f.restart ? '<span class="restart-badge">需重启</span>' : '';
  var label = '<label>' + f.label + badge + '</label>';
  var id = ' id="cfg_' + f.key + '" data-key="' + f.key + '"';

  if (f.type === 'toggle') {
    var on = (val === true || val === 'true' || val === '1');
    return '<div class="settings-field wide"><label>' + f.label + badge + '</label>'
      + '<label class="switch-row"><span class="switch"><input type="checkbox"' + id
      + (on ? ' checked' : '')
      + ' onchange="this.closest(\\'.switch-row\\').querySelector(\\'span:last-child\\').textContent=this.checked?\\'开\\':\\'关\\'">'
      + '<span class="sl"></span></span>'
      + '<span>' + (on ? '开' : '关') + '</span></label></div>';
  }
  if (f.type === 'select') {
    var s = '<div class="settings-field">' + label + '<select' + id + '>';
    f.opts.forEach(function(o){ s += '<option value="' + o.v + '"' + (val == o.v ? ' selected' : '') + '>' + o.l + '</option>'; });
    return s + '</select></div>';
  }
  if (f.type === 'textarea') {
    return '<div class="settings-field wide">' + label + '<textarea' + id + ' rows="2" placeholder="' + esc(f.ph || '') + '">' + esc(val) + '</textarea></div>';
  }
  var t = f.type === 'number' ? 'number' : (f.type === 'password' ? 'password' : 'text');
  return '<div class="settings-field">' + label + '<input type="' + t + '"' + id + ' value="' + esc(val)
    + '" placeholder="' + esc(f.ph || '') + '"></div>';
}

function filterSettings() {
  var kw = (document.getElementById('cfgSearch').value || '').trim().toLowerCase();
  var form = document.getElementById('settingsForm');
  var total = 0, shown = 0;
  form.querySelectorAll('[data-tier]').forEach(function(block){
    var hit = !kw;
    block.querySelectorAll('.settings-field').forEach(function(fd){
      var match = !kw || fd.textContent.toLowerCase().indexOf(kw) >= 0;
      fd.style.display = match ? '' : 'none';
      if (match) { hit = true; shown++; }
    });
    block.querySelectorAll('.info-line').forEach(function(fd){
      var match = !kw || fd.textContent.toLowerCase().indexOf(kw) >= 0;
      fd.style.display = match ? '' : 'none';
      if (match) hit = true;
    });
    if (kw) {
      block.style.display = hit ? '' : 'none';
      if (block.tagName === 'DETAILS') block.open = hit;
    } else {
      block.style.display = '';
      if (block.tagName === 'DETAILS') block.open = false;
    }
  });
  CFG_GROUPS.forEach(function(g){ g.fields.forEach(function(f){ if (f.key) total++; }); });
  document.getElementById('cfgSearchCount').textContent = kw ? (shown + ' / ' + total + ' 项匹配') : '';
}

// ===== 保存配置 =====
var BOOL_KEYS = ['quote_reply_prefix', 'quote_reply_native', 'mention_as_text', 'log_skipped_messages'];

function saveConfig() {
  var fields = document.querySelectorAll('#settingsForm [id^="cfg_"]');
  var data = {};
  fields.forEach(function(el){
    var key = el.getAttribute('data-key') || el.id.replace('cfg_','');
    var val;
    if (el.type === 'checkbox') val = el.checked ? 'true' : 'false';
    else val = el.value.trim();
    if (el.type === 'number') val = Number(val) || 0;
    if (BOOL_KEYS.indexOf(key) >= 0) val = (val === 'true' || val === '1');
    if (key === 'bot_nicknames') val = val ? val.split(/[,，]\\s*/).filter(Boolean) : [];
    data[key] = val;
  });

  fetch('/api/config', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data),
  }).then(function(r){return r.json()}).then(function(res){
    if (res.ok) {
      showMsg('saveMsg', '✅ 已保存，重启桥接后生效');
      toast('✅ 配置已保存', 'success');
    } else {
      showMsg('saveMsg', '❌ 保存失败');
    }
  }).catch(function(e){
    showMsg('saveMsg', '❌ 保存失败: ' + e.message);
  });
}

// ===== 成员与权限 =====
var peopleData = null;

function switchTabMembers() {
  fetch('/api/people').then(function(r){return r.json()}).then(function(d){
    peopleData = d;
    document.getElementById('membersBadge').textContent = d.astrbot_available
      ? ('AstrBot 配置已连接 · ' + d.persons.length + ' 名成员 · ' + d.groups.length + ' 个群')
      : '⚠️ 未找到 AstrBot 配置: ' + (d.astrbot_error || d.astrbot_path);
    renderPeople();
    renderGroups();
    fillAstrbotForm(d);
  }).catch(function(e){
    document.getElementById('membersBadge').textContent = '加载失败: ' + e.message;
  });
}

function copyText(text) {
  if (navigator.clipboard) { navigator.clipboard.writeText(text); }
  else {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
  }
  toast('已复制: ' + text, 'info');
}

function renderPeople() {
  if (!peopleData) return;
  var kw = (document.getElementById('memberSearch').value || '').toLowerCase();
  var admins = peopleData.admins;
  var rows = '';
  peopleData.persons.forEach(function(p){
    if (kw && p.name.toLowerCase().indexOf(kw) < 0 && p.wxid.toLowerCase().indexOf(kw) < 0) return;
    rows += '<tr>'
      + '<td class="center"><input type="checkbox" data-wxid="' + esc(p.wxid) + '"' + (admins.indexOf(p.wxid) >= 0 ? ' checked' : '') + '></td>'
      + '<td>' + esc(p.name) + (admins.indexOf(p.wxid) >= 0 ? '<span class="admin-badge">管理员</span>' : '') + '</td>'
      + '<td class="wxid">' + esc(p.wxid) + '</td>'
      + '<td class="uid">' + esc(p.uid) + '</td>'
      + '</tr>';
  });
  document.getElementById('peopleBody').innerHTML = rows || '<tr><td colspan="4" style="color:#c0aab0">没有匹配的成员（名册随消息与启动刷新）</td></tr>';
  var cnt = document.getElementById('peopleCount');
  if (cnt) cnt.textContent = peopleData.persons.length;
}

// 群总表：回复开关（立即生效） + 插嘴（写黑名单，需保存）
function renderGroups() {
  if (!peopleData) return;
  var rows = '';
  peopleData.groups.forEach(function(g){
    rows += '<tr>'
      + '<td class="center" title="勾选=机器人回复该群；取消=完全不掺和（立即生效）">'
      +   '<label class="switch"><input type="checkbox" data-mute="' + esc(g.session) + '"'
      +   (g.muted ? '' : ' checked') + ' onchange="toggleMute(this)"><span class="sl"></span></label></td>'
      + '<td class="center" title="勾选=允许它在没人 @ 时自己插嘴（需保存）">'
      +   '<input type="checkbox" data-bl="' + esc(g.gid) + '"></td>'
      + '<td class="gname">' + esc(g.name) + '</td>'
      + '<td><span class="copy-chip" data-v="' + esc(g.gid) + '" onclick="copyText(this.dataset.v)">' + esc(g.gid) + ' 📋</span></td>'
      + '<td><span class="copy-chip" data-v="' + esc(g.umo) + '" onclick="copyText(this.dataset.v)">' + esc(g.umo) + ' 📋</span></td>'
      + '</tr>';
  });
  document.getElementById('groupsBody').innerHTML = rows || '<tr><td colspan="5" style="color:#c0aab0">暂无已知群（收到消息后出现）</td></tr>';
}

function toggleMute(cb) {
  var session = cb.getAttribute('data-mute');
  var muted = !cb.checked;
  fetch('/api/session-toggle', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({session: session, muted: muted}),
  }).then(function(r){return r.json()}).then(function(res){
    if (res.ok) {
      toast(muted ? '🔇 已关闭该群回复（立即生效）' : '🔊 已恢复该群回复（立即生效）', 'success');
    } else {
      toast('❌ 操作失败: ' + res.error, 'error');
      cb.checked = !muted;
    }
  }).catch(function(e){
    toast('❌ 操作失败: ' + e.message, 'error');
    cb.checked = !muted;
  });
}

function scanAdminChecks() {
  // 把当前表格里的勾选状态并回 peopleData.admins（被搜索过滤掉的成员不受影响）
  var checked = {};
  document.querySelectorAll('#peopleBody input[type=checkbox]').forEach(function(cb){
    checked[cb.getAttribute('data-wxid')] = cb.checked;
  });
  peopleData.persons.forEach(function(p){
    if (!(p.wxid in checked)) return;
    var i = peopleData.admins.indexOf(p.wxid);
    if (checked[p.wxid] && i < 0) peopleData.admins.push(p.wxid);
    if (!checked[p.wxid] && i >= 0) peopleData.admins.splice(i, 1);
  });
}

function saveAdmins() {
  scanAdminChecks();
  var wxids = peopleData.admins.slice();
  fetch('/api/admins', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({wxids: wxids}),
  }).then(function(r){return r.json()}).then(function(res){
    if (res.ok) {
      toast('✅ 管理员已保存' + (res.synced ? '，已写入 AstrBot（重启 AstrBot 后生效）' : '，但写入 AstrBot 失败：' + res.error), res.synced ? 'success' : 'error');
      peopleData.admins = res.admins;
      renderPeople();
    } else { toast('❌ 保存失败', 'error'); }
  });
}

// 通用：把名单渲染成「群 chip 点选」；点一下选中/取消
function renderNameList(groupsId, extraId, values) {
  var vals = (values || []).map(function(x){return String(x).trim()});
  var host = document.getElementById(groupsId);
  var html = '';
  peopleData.groups.forEach(function(g){
    var hit = vals.indexOf(String(g.gid)) >= 0 || vals.indexOf(g.umo) >= 0 || vals.indexOf(g.session) >= 0;
    html += '<label class="chip' + (hit ? ' on' : '') + '">'
      + '<input type="checkbox" data-gid="' + esc(g.gid) + '"' + (hit ? ' checked' : '')
      + ' onchange="this.parentNode.classList.toggle(\\'on\\', this.checked)"><span class="dot"></span>' + esc(g.name) + '</label>';
  });
  host.innerHTML = html || '<span style="color:#c0aab0;font-size:12px">暂无已知群（收到群消息后出现）</span>';
  var extra = vals.filter(function(x){
    return !peopleData.groups.some(function(g){
      return x === String(g.gid) || x === g.umo || x === g.session;
    });
  });
  document.getElementById(extraId).value = extra.join('\\n');
}

// 通用：收集 chip 勾选 + 手动补充框
function collectNameList(groupsId, extraId) {
  var out = [];
  document.querySelectorAll('#' + groupsId + ' input[type=checkbox]:checked').forEach(function(cb){
    out.push(cb.getAttribute('data-gid'));
  });
  document.getElementById(extraId).value.split(/[,，\\n]+/).forEach(function(x){
    x = x.trim(); if (x) out.push(x);
  });
  return out;
}

function fillAstrbotForm(d) {
  // 高级区
  document.getElementById('ab_wl_enable').value = d.id_whitelist_enable ? '1' : '0';
  renderNameList('ab_wl_groups', 'ab_wl_extra', d.id_whitelist);
  renderNameList('ab_ar_groups', 'ab_ar_extra', d.ar_whitelist);
  document.getElementById('ab_ar_black_extra').value = (d.ar_blacklist || []).filter(function(x){
    x = String(x).trim();
    return x && !peopleData.groups.some(function(g){
      return x === String(g.gid) || x === g.umo || x === g.session;
    });
  }).join('\\n');
  // 全局插话
  document.getElementById('ab_ar_enable').value = d.ar_enable ? '1' : '0';
  document.getElementById('ab_ar_poss').value = d.ar_possibility;
  // 群总表的「插嘴」列 = 不在黑名单里
  var bl = (d.ar_blacklist || []).map(function(x){return String(x).trim()});
  document.querySelectorAll('#groupsBody input[data-bl]').forEach(function(cb){
    var gid = cb.getAttribute('data-bl');
    var inBl = bl.indexOf(gid) >= 0
      || peopleData.groups.some(function(g){
        if (String(g.gid) !== gid) return false;
        return bl.indexOf(g.umo) >= 0 || bl.indexOf(g.session) >= 0;
      });
    cb.checked = !inBl;
  });
  // 白名单非空时提示：表格里的「插嘴」勾选会被白名单收紧
  var warn = document.getElementById('arWhitelistWarn');
  if ((d.ar_whitelist || []).length) {
    warn.style.display = '';
    warn.className = 'hint-text amber';
    warn.innerHTML = '⚠️ <b>插话白名单不是空的</b>（高级区里勾了 ' + d.ar_whitelist.length
      + ' 条）——此时只有白名单里的群会插嘴，表格里的「插嘴」勾选会被它收紧。'
      + '如果想让表格说了算，去高级区把插话白名单清空。';
  } else {
    warn.style.display = 'none';
  }
}

function saveAstrbotCfg() {
  // 黑名单 = 表格里没勾「插嘴」的群 + 高级区手动补充的条目
  var bl = [];
  document.querySelectorAll('#groupsBody input[data-bl]').forEach(function(cb){
    if (!cb.checked) bl.push(cb.getAttribute('data-bl'));
  });
  document.getElementById('ab_ar_black_extra').value.split(/[,，\\n]+/).forEach(function(x){
    x = x.trim(); if (x) bl.push(x);
  });
  var body = {
    id_whitelist_enable: document.getElementById('ab_wl_enable').value === '1',
    id_whitelist: collectNameList('ab_wl_groups', 'ab_wl_extra'),
    ar_enable: document.getElementById('ab_ar_enable').value === '1',
    ar_possibility: parseFloat(document.getElementById('ab_ar_poss').value),
    ar_whitelist: collectNameList('ab_ar_groups', 'ab_ar_extra'),
    ar_blacklist: bl,
  };
  fetch('/api/astrbot', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body),
  }).then(function(r){return r.json()}).then(function(res){
    showMsg('abMsg', res.ok ? '✅ 已写入（重启 AstrBot 后生效）' : '❌ ' + res.error);
    toast(res.ok ? '✅ 已写入 AstrBot 配置' : '❌ 写入失败: ' + res.error, res.ok ? 'success' : 'error');
  });
}

// ===== 初始化 =====
// 支持 #settings / #members 深链：刷新后停留在原页签
var startTab = (location.hash || '').replace('#', '');
switchTab(['dashboard', 'settings', 'members'].indexOf(startTab) >= 0 ? startTab : 'dashboard');
refreshDashboard();
setInterval(refreshDashboard, 3000);
</script>
</body>
</html>"""


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            ob_connected = state._ob_ws is not None and state._ob_ws_ready.is_set()
            weflow_connected = state.bridge_instance is not None and state.bridge_instance._sse_session is not None
            log_lines = []
            try:
                with open("bridge.log", encoding="utf-8", errors="replace") as f:
                    log_lines = f.read().splitlines()[-200:]
            except Exception:
                pass
            self.send_json({
                "running": state.running,
                "paused": state.paused.is_set(),
                "send_method": config.SEND_METHOD,
                "ob_url": config.ASTRBOT_OB_URL,
                "ob_connected": ob_connected,
                "weflow_connected": weflow_connected,
                "group_reply_mode": state.group_reply_mode,
                "log": "\\n".join(log_lines),
            })
        elif self.path == "/api/config":
            try:
                with open(config.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.send_json(cfg)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        elif self.path == "/api/people":
            import people
            try:
                self.send_json(people.read_overview())
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(PAGE.encode("utf-8"))

    def do_POST(self):
        if self.path == "/start":
            from main import _start_bridge
            _start_bridge()
            self.send_json({"ok": True})
        elif self.path == "/stop":
            from main import _stop_bridge
            _stop_bridge()
            self.send_json({"ok": True})
        elif self.path == "/pause":
            state.paused.set()
            log.info("[Web] 已暂停")
            self.send_json({"ok": True})
        elif self.path == "/resume":
            state.paused.clear()
            log.info("[Web] 已恢复")
            self.send_json({"ok": True})
        elif self.path == "/mode":
            mode_order = ["all", "batch"]
            idx = mode_order.index(state.group_reply_mode) if state.group_reply_mode in mode_order else -1
            new_mode = mode_order[(idx + 1) % len(mode_order)]
            state.group_reply_mode = new_mode
            try:
                with open(config.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["group_reply_mode"] = new_mode
                with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=4)
                    f.write("\\n")
                log.info(f"[Web] 群聊模式已切换为: {new_mode}")
            except Exception as e:
                log.error(f"[Web] 保存配置失败: {e}")
            self.send_json({"ok": True, "group_reply_mode": new_mode})
        elif self.path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                new_cfg = json.loads(body)

                # 读取当前配置，仅覆盖前端传来的字段
                with open(config.CONFIG_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
                current.update(new_cfg)
                # 保留 _comment 字段
                if "_comment" not in current:
                    current["_comment"] = "微信 ↔ AstrBot 桥接 - OneBot v11 版配置"

                with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(current, f, ensure_ascii=False, indent=4)
                    f.write("\\n")

                log.info(f"[Web] 配置已保存")
                # 运行时同步 group_reply_mode（旧值 mention 归一化为 all）
                if "group_reply_mode" in new_cfg:
                    state.group_reply_mode = ("all" if new_cfg["group_reply_mode"] == "mention"
                                              else new_cfg["group_reply_mode"])

                self.send_json({"ok": True})
            except Exception as e:
                log.error(f"[Web] 保存配置异常: {e}")
                self.send_json({"ok": False, "error": str(e)}, 500)
        elif self.path == "/api/admins":
            import people
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                wxids = [str(w).strip() for w in (body.get("wxids") or []) if str(w).strip()]
                synced, msg = people.sync_admins_to_astrbot(wxids)
                self.send_json({"ok": True, "synced": synced, "message": msg,
                                "admins": people.load_admins()})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
        elif self.path == "/api/astrbot":
            import people
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                ok, msg = people.update_astrbot_settings(body)
                self.send_json({"ok": ok, "error": "" if ok else msg})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
        elif self.path == "/api/session-toggle":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                session = str(body.get("session", "")).strip()
                muted = bool(body.get("muted"))
                if not session:
                    self.send_json({"ok": False, "error": "缺少 session"}, 400)
                    return
                state.set_session_muted(session, muted)
                log.info(f"[Web] 会话 {session} 回复已{'关闭' if muted else '开启'}")
                self.send_json({"ok": True, "session": session, "muted": muted})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
        else:
            self.send_json({"ok": False}, 404)

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass
