#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_audio_scripts.py
依歷屆考題，為每個主題生成聽讀複習腳本。
使用四個選項的理由（A/B/C/D），保留法律規則，刪除所有選項/題目相關語言。
執行：python generate_audio_scripts.py
"""
import re, json
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent.parent
QDB_JS  = SCRIPT_DIR / 'js' / 'questions_data.js'
EXPL_JS = SCRIPT_DIR / 'js' / 'explanations_data.js'
OUT_JS  = SCRIPT_DIR / 'js' / 'audio_scripts.js'


def load_qdb():
    text = QDB_JS.read_text(encoding='utf-8').strip()
    text = text.removeprefix('window.QDB = ').rstrip(';\n')
    return json.loads(text)


def load_expl():
    text = EXPL_JS.read_text(encoding='utf-8')
    m = re.search(r'Object\.assign\(window\.EXPLANATIONS,\s*(\{[\s\S]*\})\s*\)', text)
    if not m:
        raise ValueError('Cannot parse explanations_data.js')
    return json.loads(m.group(1))


_CASE_SUBJ_RE = re.compile(
    r'^[甲乙丙丁][，、]|'
    r'^[甲乙丙丁](?:明知|已|係|於|不|持|以|用|將|向|在|因|看|見|雖|被|把|拿|欲|本|未|打|砍|殺|射|推|拉|跑|逃|離|開|出|進|回|去|來|取|偷|搶|騙|詐|恐|主觀|客觀)[^\n]|'
    r'^[甲乙丙丁][^，。！？\n]{0,6}(?:開槍|下手|出手|犯罪|逃逸|離去|離開|送醫|點火|放火|竊取|侵占|詐欺|行賄|受賄|殺人|傷害|強盜|竊盜|強暴|脅迫)[^\n]|'
    r'(?:^|[，。且而在」])[本][案][中係甲]|'
    r'(?:^|[，。])本題(?:中)?甲|'
    r'[，。]?且[甲乙丙丁](?:係|已|明知|客觀|主觀)|'
    r'[，、][甲乙丙丁](?:主觀|客觀|明知)[^\n]|'
    r'因[甲乙丙丁](?:客觀|主觀|明知|已著|持|點火|放火)'
)


def is_case_narrative(text: str) -> bool:
    """判斷句子是否主要在敘述特定案例事實（而非法律規則）。"""
    return bool(_CASE_SUBJ_RE.search(text))


def clean_for_audio(text):
    """
    移除所有與選項/題目有關的語言，以及案例事實敘述，只保留法律規則本身。
    """
    if not text:
        return ''

    # 1. 「故選項(X)...」整個子句（無論後面接什麼）
    text = re.sub(r'[，。]?故選項[（(][A-Da-d][)）][^。]*', '', text)

    # 2. 「，選項(X)...」在句中
    text = re.sub(r'[，、][（(]?選項[（(][A-Da-d][)）][^，。]*', '', text)

    # 3. 「(X)正確/錯誤/之陳述...」
    text = re.sub(r'[，、]?故?[（(][A-Da-d][)）][^，。]{0,30}[正確錯誤符合][^，。]*[，。]?', '', text)

    # 4a. 「本項/本選項/本題 + 任意詞 + 正確/錯誤/符合...」
    text = re.sub(r'[，、]?本[選]?項[^，。]{0,15}(?:正確|錯誤|符合|係屬)[^。]*', '', text)
    text = re.sub(r'[，、]?本題[^，。]{0,15}(?:正確|錯誤|符合)[^。]*', '', text)

    # 4b. 「此表述/陳述/說法 + 正確/錯誤」（尾端或中段）
    text = re.sub(r'[，、]?此[^，。]{0,10}(?:表述|陳述|說法)(?:正確|錯誤|有誤|為)[^。]*', '', text)
    # 「現行法下此...為錯誤/正確」
    text = re.sub(r'[，、]?現行法下[^。]*(?:錯誤|正確)[^。]*', '', text)

    # 4c. 「因此本項/本選項...」「故本項...」
    text = re.sub(r'[，、]?(?:因此|故)[^，。]{0,3}(?:本|此)[選]?[選項]?(?:表述|陳述|說法|正確|錯誤)[^。]*', '', text)

    # 5. 「故本題答案為(X)」
    text = re.sub(r'[，、]?故?本題答案[為是][（(]?[A-Da-d]?[)）]?[，。]?\s*$', '', text)

    # 6. 「符合題意」「係屬錯誤/正確」
    text = re.sub(r'[，、]?符合題意[，。]?', '', text)
    text = re.sub(r'[，、]?係屬[錯誤正確]+[，。]?', '', text)

    # 7. 「故甲/乙/丙說法正確/錯誤」
    text = re.sub(r'[，、]?故[甲乙丙丁]?[^，。]{0,12}說法[正確錯誤]+[，。]?', '', text)

    # 8. 「甲/乙陳述正確/錯誤」（尾端）
    text = re.sub(r'[，、]?[甲乙丙丁]?[^，。]{0,8}陳述[正確錯誤符合]*[，。]?\s*$', '', text)

    # 9. §XXX 法條引用格式
    text = re.sub(r'（§[\d\w]+(?:[、,]§[\d\w]+)*）', '', text)
    text = re.sub(r'§[\d\w]+', '', text)

    # 10. 短括號補充（8字以內）
    text = re.sub(r'（[^）]{1,8}）', '', text)

    # 11. 逐句過濾：移除以案例主角甲/乙為主詞的案例事實敘述
    parts = re.split(r'(?<=[。！？])', text)
    kept = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if is_case_narrative(part):
            continue
        kept.append(part)
    text = ''.join(kept)

    # 清理格式
    text = re.sub(r'。+', '。', text)
    text = re.sub(r'\s+', '', text)
    # 移除清理後殘留的孤立短詞尾句（如「現行法下。」「故。」等）
    text = re.sub(r'[，、][^，。]{1,8}[，。]$', '。', text)
    text = text.strip('，、；').strip()
    if text and text[-1] not in '。！？':
        text += '。'
    return text


def is_useful(text, min_len=18):
    """判斷是否有實質法律內容（非僅標籤或過短）。"""
    if not text or len(text) < min_len:
        return False
    # 殘留的考試語（雙重保險）
    exam_patterns = [
        r'選項[（(][A-Da-d][)）]',
        r'本[選]?項正確', r'本[選]?項錯誤', r'本項敘述',
        r'本題答案', r'符合題意', r'係屬錯誤', r'係屬正確',
        r'表述正確', r'表述錯誤', r'說法正確', r'說法錯誤',
        r'陳述正確', r'陳述錯誤',
    ]
    for p in exam_patterns:
        if re.search(p, text):
            return False
    # 若整段文字是案例事實敘述，過濾掉
    if is_case_narrative(text):
        return False
    return True


def dedupe(items, max_len=100, max_pts=16):
    """去重、截長、限數。"""
    seen, out = set(), []
    for s in items:
        s = s.strip()
        if not s or len(s) < 18:
            continue
        if len(s) > max_len:
            # 在句子結構處截斷
            for ch in ('。', '，', '；'):
                idx = s[:max_len].rfind(ch)
                if idx > 30:
                    s = s[:idx + 1]
                    break
            else:
                s = s[:max_len] + '。'
        key = s[:16]
        if key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= max_pts:
            break
    return out


def main():
    print('Loading QDB...')
    qdb  = load_qdb()
    print('Loading explanations...')
    expl = load_expl()

    q_by_id = {q['id']: q for q in qdb['questions']}
    topics  = qdb['topics']

    # topic_id -> list of {year, reasons(list), supplement}
    topic_data = defaultdict(list)

    for qid, e in expl.items():
        if qid not in q_by_id:
            continue
        q   = q_by_id[qid]
        tid = q.get('topic')
        if not tid or tid not in topics:
            continue

        # ── 收集四個選項的理由（A/B/C/D），都是法律知識 ──────
        all_reasons = []
        opts = e.get('options', {})
        answer_letter = q.get('answer', '')
        # 正確選項優先加入，其次其他選項
        priority = ([answer_letter] if answer_letter else []) + \
                   [l for l in 'ABCD' if l != answer_letter]
        for letter in priority:
            if letter in opts:
                r = (opts[letter].get('reason') or '').strip()
                r = clean_for_audio(r)
                if is_useful(r):
                    all_reasons.append(r)

        supplement = clean_for_audio((e.get('supplement') or '').strip())

        topic_data[tid].append({
            'year':       q['year'],
            'reasons':    all_reasons,
            'supplement': supplement if is_useful(supplement) else '',
            'concept':    (e.get('concept') or '').strip(),
        })

    scripts = {}

    for tid, info in topics.items():
        entries = topic_data.get(tid, [])
        if not entries:
            continue

        entries.sort(key=lambda x: -x['year'])  # 新年份優先

        law_sub    = info.get('law_subject', '')
        name       = info.get('name', tid)
        short      = info.get('short_name') or name.split('｜')[-1]
        exam_count = len(entries)

        # ── 彙整所有法律規則（去重）────────────────────────────
        all_pts = []
        seen_k  = set()
        for ent in entries:
            for r in ent['reasons']:
                k = r[:16]
                if k not in seen_k:
                    seen_k.add(k)
                    all_pts.append(r)
            s = ent['supplement']
            if s:
                k = s[:16]
                if k not in seen_k:
                    seen_k.add(k)
                    all_pts.append(s)

        # 始終嘗試用 concept 欄位補充（提供更多法律概念要點）
        for ent in entries:
            c = (ent.get('concept') or '').strip()
            if c and len(c) >= 15:
                # concept 通常較短且純概念，不需要 clean_for_audio 全流程，僅做基本清理
                c_clean = re.sub(r'[，、]?(?:故|因此)?本[選]?項[^。]*', '', c).strip()
                c_clean = c_clean.strip('，、；').strip()
                if c_clean and len(c_clean) >= 15 and c_clean[:16] not in seen_k:
                    seen_k.add(c_clean[:16])
                    all_pts.append(c_clean)

        points = dedupe(all_pts, max_pts=25)
        if not points:
            continue

        scripts[tid] = {
            'title':      short,
            'subject':    law_sub,
            'exam_count': exam_count,
            'points':     points,
        }

    out_json = json.dumps(scripts, ensure_ascii=False, indent=2)
    output = (
        '// 聽讀複習腳本 — 由 generate_audio_scripts.py 自動產生\n'
        '// 素材：各題四個選項的理由（純法律規則，已移除選項/題目語言）\n'
        '// 請勿手動修改，重跑本腳本即可更新\n'
        f'window.AUDIO_SCRIPTS = {out_json};\n'
    )
    OUT_JS.write_text(output, encoding='utf-8')

    total_pts = sum(len(v['points']) for v in scripts.values())
    covered   = len(scripts)
    print(f'Done: {covered} topics, {total_pts} total points')
    print(f'Avg: {total_pts/covered:.1f} pts/topic')


if __name__ == '__main__':
    main()
