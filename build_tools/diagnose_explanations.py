#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_explanations.py
全面診斷「詳解」資料夾的狀況，並產生詳細報告。
"""
import re, json, sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent.parent
QDB_JS     = SCRIPT_DIR / 'js' / 'questions_data.js'
EXP_JS     = SCRIPT_DIR / 'js' / 'explanations_data.js'
MD_DIR     = SCRIPT_DIR.parent / '詳解'
HEADER_RE  = re.compile(r'【(\d+)\s*年[^】]{0,30}?第\s*(\d+)\s*題[^】]*?】')

SUBJECT_TO_SUBJ = {
    '刑法':       'criminal',     '刑事訴訟法': 'criminal',   '法律倫理':   'criminal',
    '憲法':       'constitutional','行政法':     'constitutional','國際公法':   'constitutional',
    '國際私法':   'constitutional','民法':       'civil',      '民事訴訟法': 'civil',
    '公司法':     'commercial',   '票據法':     'commercial', '海商法':     'commercial',
    '保險法':     'commercial',   '強制執行法': 'commercial', '證券交易法': 'commercial',
    '法學英文':   'commercial',
}

def clean_text(text):
    return "".join(c for c in text if ('\u4e00' <= c <= '\u9fff') or c.isalpha())

def load_qdb():
    text = QDB_JS.read_text(encoding='utf-8').strip()
    text = text.removeprefix('window.QDB = ').rstrip(';\n')
    return json.loads(text)

def load_explanations():
    text = EXP_JS.read_text(encoding='utf-8')
    m = re.search(r'Object\.assign\(window\.EXPLANATIONS,\s*(\{[\s\S]*\})\s*\)', text)
    if m:
        try:
            return set(json.loads(m.group(1)).keys())
        except Exception as e:
            pass
    # 格式是 window.EXPLANATIONS["key"] = "..."; 逐行抓 key
    keys = re.findall(r'window\.EXPLANATIONS\["([^"]+)"\]', text)
    return set(keys)


def main():
    qdb = load_qdb()
    exp = load_explanations()
    
    # 建立 QDB 索引
    qdb_index = {}
    qdb_by_subject = defaultdict(list)
    for q in qdb['questions']:
        key = f"{q['year']}_{q['subject']}_{q['num']}"
        qdb_index[key] = q
        qdb_by_subject[q['subject']].append(q)
    
    total_q = len(qdb['questions'])
    total_exp = len(exp)
    
    print("=" * 60)
    print("【詳解資料庫診斷報告】")
    print("=" * 60)
    print(f"一試考古題題庫：{total_q} 題")
    print(f"目前已解析詳解：{total_exp} 條")
    print(f"覆蓋率：{total_exp/total_q*100:.1f}%")
    print()
    
    # 找出有詳解但找不到對應題目的（錯配）
    mismatched = []
    for key in exp:
        if key not in qdb_index:
            mismatched.append(key)
    
    # 找出題庫裡有但詳解沒有的（缺漏）
    missing = []
    for key in qdb_index:
        if key not in exp:
            missing.append(key)
    
    print(f"── 錯配（詳解標籤在題庫中找不到對應題目）：{len(mismatched)} 條")
    if mismatched[:10]:
        for k in sorted(mismatched)[:10]:
            print(f"   ❌ {k}")
        if len(mismatched) > 10:
            print(f"   ... 還有 {len(mismatched)-10} 條")
    print()
    
    print(f"── 缺漏（題庫有但詳解沒有）：{len(missing)} 題")
    # 依科目分類缺漏狀況
    missing_by_subj = defaultdict(list)
    for key in missing:
        parts = key.split('_')
        if len(parts) >= 2:
            subj = parts[1]
            missing_by_subj[subj].append(key)
    
    for subj, ks in sorted(missing_by_subj.items()):
        years = sorted(set(k.split('_')[0] for k in ks), reverse=True)
        print(f"   {subj}: 缺 {len(ks)} 題 (年份分布: {', '.join(years[:5])}{'...' if len(years)>5 else ''})")
    print()
    
    # 逐檔案狀況
    print(f"── 各詳解檔案狀況：")
    for filepath in sorted(MD_DIR.glob('*.md')):
        stem = filepath.stem
        subj_code = SUBJECT_TO_SUBJ.get(stem)
        if not subj_code:
            print(f"   {stem}.md → 找不到對應大科，跳過")
            continue
        
        content = filepath.read_text(encoding='utf-8')
        headers = list(HEADER_RE.finditer(content))
        total_in_file = len(headers)
        
        matched_count = 0
        mismatch_count = 0
        correct_qs = [q for q in qdb['questions'] if q['subject'] == subj_code]
        correct_lookup = {}
        for q in correct_qs:
            cq = clean_text(q['question'])
            for length in [15, 20]:
                feat = cq[:length]
                if len(feat) == length and feat not in correct_lookup:
                    correct_lookup[feat] = q
        
        for m in headers:
            year = int(m.group(1))
            num  = int(m.group(2))
            block_start = m.end()
            block_content = content[m.start():].strip()
            content_after = block_content[len(m.group(0)):].strip()
            
            # 跳過 metadata 行
            lines = content_after.splitlines()
            q_stem_raw = ""
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                if any(line_str.startswith(p) for p in ['重要度', '難度', '選擇題', '單選題', '考點', '★', '▲', '■', '●', '⭐', '🔥', '#']):
                    continue
                q_stem_raw = line_str
                break
            
            if not q_stem_raw:
                continue
            
            clean_stem = clean_text(q_stem_raw)
            found = None
            for length in [20, 15]:
                feat = clean_stem[:length]
                if len(feat) >= length and feat in correct_lookup:
                    found = correct_lookup[feat]
                    break
            
            if found:
                real_key = f"{found['year']}_{found['subject']}_{found['num']}"
                if found['year'] == year and found['num'] == num:
                    matched_count += 1
                else:
                    mismatch_count += 1
            else:
                # 無法比對到原始試題（可能是AI大幅改寫）
                mismatch_count += 1
        
        total_subj_q = len(correct_qs)
        in_exp = sum(1 for q in correct_qs if f"{q['year']}_{q['subject']}_{q['num']}" in exp)
        status = "✅" if mismatch_count == 0 else "⚠️ "
        print(f"   {status} {stem}.md → 共 {total_in_file} 題，對齊 {matched_count} 題，疑似錯配 {mismatch_count} 題｜詳解已覆蓋 {in_exp}/{total_subj_q} 題")
    print()
    print("診斷完成！")

if __name__ == '__main__':
    main()
