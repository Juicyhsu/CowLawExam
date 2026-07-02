#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_flashcards.py
從 explanations_data.js 的 concept/supplement 欄位，
按主題彙整考點，產生 js/generated_flashcards.js

執行：python generate_flashcards.py
"""
import re, json
from pathlib import Path
from collections import defaultdict

_ARTIFACT_PATS = [
    re.compile(r'正確答案[：:][A-Da-d]'),
    re.compile(r'逐項分析[：:][：\s]*'),
    re.compile(r'[oO]\s+[A-D]\s+(?:公司|保險|甲|乙|丙|丁)'),
    re.compile(r'\$[^$]+\$'),                          # LaTeX math
    re.compile(r'本題選項[稱謂謂稱][^。]*'),
    re.compile(r'本題[（(]?[A-D][)）][^。]{0,50}'),
    re.compile(r'【[（(][A-D][)）]】[❌✓]?[^】]*'),      # 【(D)】❌...
    re.compile(r'^即正確答案[。，]?\s*', re.M),
    re.compile(r'答案[（(][^)）]+[)）]\s*理由[：:]'),
    re.compile(r'非正確答案[）。，]?'),
    re.compile(r'^[（(][A-D][)）]\s*[正確錯誤]+[：:：]\s*', re.M),  # (C) 正確：
    re.compile(r'^[（(]?[A-D][)）]\s*(?:公司|保險|甲|乙|丙|丁)[^。]{0,80}', re.M),  # A 公司...分析行
    re.compile(r'^[，、][（(][A-D][)）][、，][^：]*[錯誤正確]+[：:：]\s*', re.M),   # ，(A)、(C)、(D) 錯誤：
    re.compile(r'^敘述[正確錯誤]+[）)。，]+\s*', re.M),     # 敘述錯誤）。
    re.compile(r'^法條備註[：:：]\s*$', re.M),             # 孤立的「法條備註：」行
    re.compile(r'^📌法條備註[：:：]\s*$', re.M),           # 📌法條備註：行
    re.compile(r'^[oO]\t.*', re.M),                    # o\t 格式案例分析bullet
    re.compile(r'^-\t.*', re.M),                       # -\t 格式案例分析bullet
    re.compile(r'^\t.*', re.M),                        # 縮排的案例細節行
    re.compile(r'^綜合結論[：:].*', re.M),               # 「綜合結論：」行（case-specific）
    re.compile(r'^逾期提示之失權效果分析[：:].*', re.M),
    re.compile(r'^(?:各票據簽名人|己之權利狀態|背書人\w之責任)[：:].*', re.M),
]

# 案例主角正則（用於過濾 reason 中的案例事實敘述）
_CASE_SUBJ_RE = re.compile(
    r'^[甲乙丙丁][，、]|'
    r'^[甲乙丙丁](?:明知|已|係|於|不|持|以|用|將|向|在|因|看|見|雖|被|欲|本|未|打|砍|殺|射|推|逃|離|開|出|取|偷|搶|騙|主觀|客觀)[^\n]|'
    r'(?:^|[，。且而在」])[本][案][中係甲]|'
    r'[，。]?且[甲乙丙丁](?:係|已|明知|客觀|主觀)|'
    r'[，、][甲乙丙丁](?:主觀|客觀|明知)[^\n]|'
    r'因[甲乙丙丁](?:客觀|主觀|明知|已著|持|點火)|'
    r'本題選(?:此|[A-Da-d])[）)][：，]|'
    r'本選項(?:所述|所描述|稱|係|為)[^。]{0,60}(?:正確|錯誤|係屬|不符|違反|有誤)'
)


def _is_case_narrative(text: str) -> bool:
    return bool(_CASE_SUBJ_RE.search(text))


def _clean_text(text: str) -> str:
    """移除考題語言汙染，適用於 concept 和 correct_reason。"""
    if not text:
        return ''
    for pat in _ARTIFACT_PATS:
        text = pat.sub('', text)
    # 移除孤立的「正確答案」行
    lines = [l for l in text.splitlines() if not re.match(r'\s*正確答案\s*[：:][A-Da-d]?\s*$', l)]
    text = '\n'.join(lines).strip()
    # 清除每行開頭的殘留標點
    text = re.sub(r'^([✓•⚠]\s*)[，。；：、]+\s*', r'\1', text, flags=re.M)
    # 清除多餘空白行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _extract_legal_rule(reason: str) -> str:
    """
    從 reason 文字中萃取純法律規則部分。
    - 過濾掉以甲/乙為主詞的案例事實句子
    - 只保留說明法律規則的句子
    - 結果若太短（< 20字）則捨棄
    """
    if not reason:
        return ''
    # 先套用基本清理
    reason = _clean_text(reason)
    # 逐句過濾
    sentences = re.split(r'(?<=[。！？])', reason)
    kept = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 10:
            continue
        if _is_case_narrative(s):
            continue
        # 移除「選項(X)...」「本選項...正確/錯誤」等殘留
        s = re.sub(r'[，、]?(?:故)?選項[（(][A-Da-d][)）][^。]*', '', s)
        s = re.sub(r'[，、]?本[選]?項[^，。]{0,15}(?:正確|錯誤|符合|係屬)[^。]*', '', s)
        s = re.sub(r'本選項(?:係|為|所述|所描述|稱)[^。]*', '', s)
        s = re.sub(r'本題選(?:此|[A-Da-d])[）)][：，][^，。]*', '', s)
        s = re.sub(r'[，、]?係屬[錯誤正確]+[，。]?', '', s)
        s = re.sub(r'[，]?故[（(][A-Da-d][)）][^。]*', '', s)
        s = re.sub(r'[，]?符合題意[，。]?', '', s)
        s = re.sub(r'[，、]?有誤[——\-][^。]*', '', s)
        s = s.strip('，、；').strip()
        if s and len(s) >= 15:
            kept.append(s if s.endswith('。') else s + '。')
    return ' '.join(kept).strip()


_clean_concept = _clean_text  # 別名相容

SCRIPT_DIR = Path(__file__).parent.parent
QDB_JS     = SCRIPT_DIR / 'js' / 'questions_data.js'
EXPL_JS    = SCRIPT_DIR / 'js' / 'explanations_data.js'
OUT_JS     = SCRIPT_DIR / 'js' / 'generated_flashcards.js'

# 主題重要度 → importance 字串
def imp_label(v):
    return 'high' if v >= 5 else 'medium' if v >= 3 else 'low'


def load_qdb():
    text = QDB_JS.read_text(encoding='utf-8').strip()
    text = text.removeprefix('window.QDB = ').rstrip(';\n')
    return json.loads(text)


def load_expl():
    text = EXPL_JS.read_text(encoding='utf-8')
    m = re.search(r'Object\.assign\(window\.EXPLANATIONS,\s*(\{[\s\S]*\})\s*\)', text)
    return json.loads(m.group(1))


def main():
    qdb  = load_qdb()
    expl = load_expl()

    # ── 建立 qid → (year, num, topic, law_subject) 索引 ──
    q_info = {}
    for q in qdb['questions']:
        q_info[q['id']] = q

    topics = qdb['topics']  # topic_id → {name, short_name, law_subject, importance, kw}

    # ── 按主題彙整考點 ──────────────────────────────────
    # topic_id → list of (year, num, concept, supplement, law_basis)
    topic_entries = defaultdict(list)

    for qid, e in expl.items():
        if qid not in q_info:
            continue
        q   = q_info[qid]
        tid = q.get('topic')
        if not tid or tid not in topics:
            continue

        concept    = _clean_concept((e.get('concept') or '').strip())
        supplement = (e.get('supplement') or '').strip()
        law_basis  = (e.get('law_basis') or '').strip()

        if not concept:
            continue

        # 正確選項的理由（最完整的法律規則正向陳述）
        answer_letter  = q.get('answer', '')
        correct_reason = ''
        opts = e.get('options', {})
        if answer_letter and answer_letter in opts:
            correct_reason = _clean_text((opts[answer_letter].get('reason') or '').strip())

        topic_entries[tid].append({
            'year':           q['year'],
            'num':            q['num'],
            'concept':        concept,
            'supplement':     supplement,
            'law_basis':      law_basis,
            'correct_reason': correct_reason,
        })

    # ── 生成每個主題的卡片 ─────────────────────────────
    cards = []
    for tid, info in topics.items():
        entries = topic_entries.get(tid, [])
        if not entries:
            continue

        # 年份由新到舊，同年份按題號排
        entries.sort(key=lambda x: (-x['year'], x['num']))

        law_sub   = info.get('law_subject', info.get('law_sub', ''))
        name      = info.get('name', tid)
        short     = info.get('short_name') or name.split('｜')[-1]
        kws       = info.get('kw', [])
        imp       = info.get('importance', 3)
        imp_str   = imp_label(imp)

        # ── 去重並收集各種資訊 ──────────────────────────
        seen_c   = set()
        seen_s   = set()
        seen_law = set()
        seen_r   = set()
        uniq_concepts    = []
        uniq_supplements = []
        uniq_rules       = []   # 萃取後的純法律規則（取代原有的答題關鍵）
        law_refs         = []

        for ent in entries:
            c = ent['concept'].strip()
            if c and c not in seen_c:
                seen_c.add(c)
                uniq_concepts.append(c)

            s = ent['supplement'].strip() if ent['supplement'] else ''
            if s and s not in seen_s and s != '---':
                seen_s.add(s)
                uniq_supplements.append(s)

            lb = ent['law_basis'].strip() if ent['law_basis'] else ''
            if lb and lb not in seen_law:
                seen_law.add(lb)
                law_refs.append(lb)

            # 從正確選項理由中萃取純法律規則（過濾案例事實敘述）
            r = ent.get('correct_reason', '').strip()
            if r:
                r_clean = _extract_legal_rule(r)
                if r_clean and len(r_clean) >= 20 and r_clean not in seen_r and r_clean not in seen_c:
                    seen_r.add(r_clean)
                    uniq_rules.append(r_clean)

        law_basis_str = '；'.join(law_refs[:4])

        # ── Back：法律概念複習導向（純法律知識，不含解題語言）──
        lines = []

        # 必記法條（若有）
        if law_refs:
            lines.append('📌 ' + '　'.join(law_refs[:3]))
            lines.append('')

        # 核心考點（每點一行，純概念描述）
        lines.append('【核心考點】')
        for c in uniq_concepts[:15]:
            lines.append('• ' + c)

        # 重要規則（從正確選項理由萃取出的純法律規則，不含選項評價語言）
        if uniq_rules:
            lines.append('')
            lines.append('【重要規則】')
            for r in uniq_rules[:10]:
                lines.append('• ' + r)

        # 補充注意（若有）
        if uniq_supplements:
            lines.append('')
            lines.append('【注意事項】')
            for s in uniq_supplements[:6]:
                lines.append('⚠ ' + s)

        back = '\n'.join(lines)
        tags = kws[:8]

        cards.append({
            'id':          f'gen_{tid}',
            'topic':       tid,
            'law_subject': law_sub,
            'front':       short,           # 直接用主題名，不加前綴
            'back':        back,
            'law_basis':   law_basis_str,
            'tags':        tags,
            'importance':  imp_str,
        })

    # ── 輸出 ───────────────────────────────────────────
    header = (
        '// 考點彙整卡片 — 由 generate_flashcards.py 自動產生\n'
        '// 請勿手動修改，重跑腳本即可更新\n'
        '// 此檔僅補充 flashcards.js 未覆蓋之主題，手動卡片優先\n'
    )

    # 轉成 JS：把 \n 保留為字串內換行
    def card_to_js(c):
        return json.dumps(c, ensure_ascii=False, indent=2)

    js_cards = ',\n'.join(card_to_js(c) for c in cards)
    output = (
        header +
        '// 考點彙整卡放在獨立陣列，app.js 會在手動卡之後附加顯示\n'
        'window.GENERATED_FLASHCARDS = [\n' +
        js_cards + '\n'
        '];\n'
    )

    OUT_JS.write_text(output, encoding='utf-8')
    print('Generated ' + str(len(cards)) + ' topic cards -> ' + str(OUT_JS))
    print('Topics covered: ' + str(len(set(c['topic'] for c in cards))))


if __name__ == '__main__':
    main()
