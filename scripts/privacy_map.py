# -*- coding: utf-8 -*-
"""git 历史隐私清洗的替换映射（git-filter-repo 的 callbacks 文件）。

原则：
  · 真实群友昵称 / 群名 / 真实 UID / 真实 wxid → 占位符
  · RulerCordelius 是用户公开 ID、项目代号的一部分 → **保留**（用户明确说过不是隐私）
  · 通用技术词（Mon3tr 是 bot 角色名 → 保留；"博士"是称呼 → 保留）
"""
