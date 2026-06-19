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

SCRIPT_DIR = Path(__file__).parent
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

        concept    = (e.get('concept') or '').strip()
        supplement = (e.get('supplement') or '').strip()
        law_basis  = (e.get('law_basis') or '').strip()

        if not concept:
            continue

        topic_entries[tid].append({
            'year':       q['year'],
            'num':        q['num'],
            'concept':    concept,
            'supplement': supplement,
            'law_basis':  law_basis,
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
        uniq_concepts    = []   # (concept_text, is_supplement_related)
        uniq_supplements = []
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

        law_basis_str = '；'.join(law_refs[:4])

        # ── Back：考生複習導向 ──────────────────────────
        lines = []

        # 必記法條（若有）
        if law_refs:
            lines.append('📌 ' + '　'.join(law_refs[:3]))
            lines.append('')

        # 核心考點（精簡，每點一行，不附年份）
        lines.append('【核心考點】')
        for c in uniq_concepts[:12]:
            lines.append('• ' + c)

        # 補充注意（若有）
        if uniq_supplements:
            lines.append('')
            lines.append('【注意事項】')
            for s in uniq_supplements[:5]:
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
