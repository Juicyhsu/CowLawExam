#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_alignment.py
比對「詳解 MD」與「一試考古題原始資料」的題幹是否對齊，找出標錯題號或年份的題目。
"""
import re, json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
QDB_JS     = SCRIPT_DIR / 'js' / 'questions_data.js'
MD_DIR     = SCRIPT_DIR.parent / '詳解'
HEADER_RE  = re.compile(r'【(\d+)\s*年[^】]{0,30}?第\s*(\d+)\s*題[^】]*?】')

SUBJECT_TO_SUBJ = {
    '刑法':       'criminal',
    '刑事訴訟法': 'criminal',
    '法律倫理':   'criminal',
    '憲法':       'constitutional',
    '行政法':     'constitutional',
    '國際公法':   'constitutional',
    '國際私法':   'constitutional',
    '民法':       'civil',
    '民事訴訟法': 'civil',
    '公司法':     'commercial',
    '票據法':     'commercial',
    '海商法':     'commercial',
    '保險法':     'commercial',
    '強制執行法': 'commercial',
    '證券交易法': 'commercial',
    '法學英文':   'commercial',
}

def load_qdb():
    text = QDB_JS.read_text(encoding='utf-8').strip()
    text = text.removeprefix('window.QDB = ').rstrip(';\n')
    return json.loads(text)

def clean_question_text(text):
    # 僅保留中文字與英文字母，忽略標點、空白及數字，取前 20 個字比對
    text = "".join(c for c in text if ('\u4e00' <= c <= '\u9fff') or c.isalpha())
    return text[:20]


def main():
    qdb = load_qdb()
    # 建立正確資料庫索引：(year, subj, num) -> question_stem
    correct_db = {}
    # 同時建立 (year, subj) -> list of (num, question_stem) 用於反向尋找
    by_subject_year = {}
    
    for q in qdb['questions']:
        key = (q['year'], q['subject'], q['num'])
        stem = q['question'].strip()
        correct_db[key] = stem
        
        sy_key = (q['year'], q['subject'])
        if sy_key not in by_subject_year:
            by_subject_year[sy_key] = []
        by_subject_year[sy_key].append((q['num'], stem))

    mismatches = []
    
    for md_file in sorted(MD_DIR.glob('*.md')):
        subj = SUBJECT_TO_SUBJ.get(md_file.stem)
        if not subj:
            continue
            
        content = md_file.read_text(encoding='utf-8')
        matches = list(HEADER_RE.finditer(content))
        
        for i, m in enumerate(matches):
            year = int(m.group(1))
            num  = int(m.group(2))
            
            block_start = m.end()
            block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            block       = content[block_start:block_end].strip()
            
            # 從 block 中抓取題目內容（直到選項 (A) 出現前）
            q_text_match = re.split(r'\n[ \t]*\([ABCD]\)', block)[0].strip()
            # 移除題號標記如果有的話
            q_text_clean = clean_question_text(q_text_match)
            
            # 1. 檢查這個年份與題號在正確資料庫中是否存在
            key = (year, subj, num)
            correct_text = correct_db.get(key)
            
            if not correct_text:
                mismatches.append({
                    'file': md_file.name,
                    'header': f"【{year}年 第{num}題】",
                    'type': '不存在此題號/年份',
                    'md_text': q_text_match[:50] + '...',
                    'suggested': '無此題'
                })
                continue
                
            correct_clean = clean_question_text(correct_text)
            
            # 2. 比對題幹是否相符
            if q_text_clean != correct_clean:
                # 嘗試在該年該考科中，找出這題究竟是第幾題
                sy_key = (year, subj)
                found_real_num = None
                for real_num, real_text in by_subject_year.get(sy_key, []):
                    if clean_question_text(real_text) == q_text_clean:
                        found_real_num = real_num
                        break
                
                # 如果同一年找不到，嘗試在所有年份中尋找
                if not found_real_num:
                    for (ry, rs, rn), rtext in correct_db.items():
                        if rs == subj and clean_question_text(rtext) == q_text_clean:
                            found_real_num = (ry, rn)
                            break
                
                suggest = ""
                if found_real_num:
                    if isinstance(found_real_num, tuple):
                        suggest = f"實際應為：【{found_real_num[0]}年 第{found_real_num[1]}題】"
                    else:
                        suggest = f"實際應為：【{year}年 第{found_real_num}題】"
                else:
                    suggest = "找不到匹配題目，請檢查題幹內容是否正確"

                mismatches.append({
                    'file': md_file.name,
                    'header': f"【{year}年 第{num}題】",
                    'type': '題幹與正確題目不符',
                    'md_text': q_text_match[:40] + '...',
                    'correct_expected': correct_text[:40] + '...',
                    'suggested': suggest
                })

    print(f"\n=== 比對完成，發現 {len(mismatches)} 處不對齊的題目 ===")
    for item in mismatches:
        print(f"檔案: {item['file']}")
        print(f"  標籤: {item['header']} | 問題類型: {item['type']}")
        print(f"  詳解檔內容: {item['md_text']}")
        if 'correct_expected' in item:
            print(f"  期望正確題: {item['correct_expected']}")
        print(f"  建議修正: {item['suggested']}")
        print("-" * 50)

if __name__ == '__main__':
    main()
