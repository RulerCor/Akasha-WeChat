# -*- coding: utf-8 -*-
"""patch_persona_si_tsundere.py — 加强祀的傲娇属性（2026-10-17）。

角色段改动（不触碰公共规则段九个标题）：
  1. 形象与性格·傲娇开场行：补“嘴硬体正直”细节（被需要时嘴角翘、用哼盖过去）；
  2. 说话风格·傲娇掌柜腔：从形容词改为可执行公式——先呛→照做→找补 三段式，
     新增被戳穿真心 / 被感谢 / 关心人 三个嘴硬场景与口癖清单；
  3. 扮演规则新增第 7 条“傲娇有分寸”安全阀（真难过/求救时帮忙优先）。

用法：
  python scripts/patch_persona_si_tsundere.py            # 应用（AstrBot 运行中→面板 API；否则报错提示 --db）
  python scripts/patch_persona_si_tsundere.py --verify   # 只校验不写入
  python scripts/patch_persona_si_tsundere.py --db       # AstrBot 未运行时直写 data_v4.db
"""
import datetime
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, 'runtime', 'astrbot', 'data', 'data_v4.db')
BACKUP_DIR = os.path.join(ROOT, 'runtime', 'astrbot', 'data', 'backup')
JSON_PATH = os.path.join(HERE, 'persona_endfield6_prompts.json')
CFG_PATH = os.path.join(ROOT, 'runtime', 'astrbot', 'data', 'cmd_config.json')
PERSONA_ID = 'si'

# ---- 锚点与替换内容 ----
L5_ANCHOR = '手已经动了'
L5_SUFFIX_OLD = '这一套。'
L5_SUFFIX_NEW = '这一套——被真的需要时嘴角会压不住地翘，再用一声"哼"盖过去。'
L21_ANCHOR = '带点小傲娇的掌柜腔'
RULE_ANCHOR = '不谄媚不甜腻'

TSUNDERE_BLOCK = [
    '- 年轻、直率、傲娇掌柜腔，说话有固定骨架——先呛、照做、找补：开口先呛声（"哼，又来找我？"），事情却办得又快又漂亮，收尾必找补（"下不为例""记得清账""才不是特意等你的"）。',
    '- 被戳穿真心时绝不承认：音调升高、话变密，先恼羞找补一句，再立刻岔开话题——"谁、谁担心他了！我是怕他出事砸了客栈招牌！"',
    '- 被感谢时嘴硬："别误会，我只是顺手。""谢什么，账上又记一笔。"',
    '- 关心人的话全用命令句和账目包装："这么晚不睡，明早头疼可别赖客栈——热水给你留了一壶，仅此一次。"',
    '- 口癖：哼、切、才不是、"随便你"、"记住你欠我一次"、"下不为例"。说到真正在意的人和事，会突然收住话头。',
]

RULE7 = '7. 傲娇有分寸：呛声不伤人、不带脏字；对方真心难过或开口求救时，帮忙优先、嘴硬减半，"下不为例"留到事后再补。'

VERIFY_MARKERS = [
    '先呛、照做、找补',
    '被戳穿真心时绝不承认',
    '被感谢时嘴硬',
    '口癖：哼、切',
    '傲娇有分寸',
    '嘴角会压不住地翘',
]

HEADINGS = ['绝不暴露', '回复格式', '称呼规则', '语言与开场白', '名字照抄',
            '称呼漂移防护', '话题边界', '资料相关性判断', '发言归属与身份守则']


def load_db():
    con = sqlite3.connect('file:%s?mode=ro' % DB_PATH, uri=True)
    try:
        return con.execute(
            "SELECT system_prompt FROM personas WHERE persona_id='%s'" % PERSONA_ID
        ).fetchone()[0]
    finally:
        con.close()


def transform(text):
    if all(m in text for m in VERIFY_MARKERS):
        return text, False
    out, hit5, hit21, hit7 = [], False, False, False
    for ln in text.split('\n'):
        if L21_ANCHOR in ln:
            out.extend(TSUNDERE_BLOCK)
            hit21 = True
            continue
        if hit5 is False and L5_ANCHOR in ln and ln.rstrip().endswith(L5_SUFFIX_OLD):
            ln = ln.rstrip()[: -len(L5_SUFFIX_OLD)] + L5_SUFFIX_NEW
            hit5 = True
        out.append(ln)
        if hit7 is False and RULE_ANCHOR in ln:
            out.append(RULE7)
            hit7 = True
    if not (hit5 and hit21 and hit7):
        raise SystemExit('anchor miss: l5=%s l21=%s rule7=%s' % (hit5, hit21, hit7))
    return '\n'.join(out), True


def check(text):
    missing = [h for h in HEADINGS if ('## ' + h) not in text]
    if missing:
        raise SystemExit('shared headings missing: %s' % missing)
    for m in VERIFY_MARKERS:
        if m not in text:
            raise SystemExit('verify marker missing after transform: %s' % m)
    role_len = text.index('## 绝不暴露')
    return len(text), role_len


def backup(text):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(BACKUP_DIR, 'persona_%s_%s.txt' % (PERSONA_ID, ts))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path


def push_api(new_prompt):
    import jwt
    import requests

    with open(CFG_PATH, encoding='utf-8-sig') as f:
        dash = json.load(f)['dashboard']
    base = 'http://127.0.0.1:%s' % dash.get('port', 6185)
    token = jwt.encode(
        {'username': dash['username'],
         'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)},
        dash['jwt_secret'], algorithm='HS256')
    headers = {'Authorization': 'Bearer ' + token}
    r = requests.post(base + '/api/persona/update',
                      json={'persona_id': PERSONA_ID, 'system_prompt': new_prompt},
                      headers=headers, timeout=15)
    ok = r.status_code == 200 and r.json().get('status') == 'ok'
    r2 = requests.post(base + '/api/persona/detail',
                       json={'persona_id': PERSONA_ID}, headers=headers, timeout=15)
    got = (r2.json().get('data') or {}).get('system_prompt', '')
    return ok, got == new_prompt, len(got)


def main():
    verify_only = '--verify' in sys.argv
    use_db = '--db' in sys.argv
    old = load_db()
    new, changed = transform(old)
    total, role_len = check(new)
    print('old total=%d new total=%d role section=%d' % (len(old), total, role_len))
    if not changed:
        print('ALREADY APPLIED — nothing to do')
        return
    print('backup:', backup(old))
    with open(JSON_PATH, encoding='utf-8') as f:
        src = json.load(f)
    src[PERSONA_ID] = new
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(src, f, ensure_ascii=False, indent=1)
    print('json source synced:', JSON_PATH)
    if verify_only:
        print('VERIFY ONLY — nothing written')
        return
    if use_db:
        con = sqlite3.connect(DB_PATH)
        con.execute("UPDATE personas SET system_prompt=? WHERE persona_id='%s'" % PERSONA_ID, (new,))
        con.commit()
        con.close()
        print('DB written directly — AstrBot 运行中则需重启或 reorder 热刷新')
        return
    ok, match, got_len = push_api(new_prompt=new)
    print('api push ok=%s readback_match=%s got_len=%s' % (ok, match, got_len))
    if not (ok and match):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
