#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_align_headers.py
根據「一試考古題」的正確題目內容，自動比對並修正「詳解/*.md」中標錯的題號與年份。
"""
import re, json, sys
from pathlib import Path

# 強制終端機輸出採用 UTF-8，防止 Windows 環境下印出 Emoji 或中文字元時發生 UnicodeEncodeError
sys.stdout.reconfigure(encoding='utf-8')

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

SCRIPT_DIR = Path(__file__).parent.parent
QDB_JS     = SCRIPT_DIR / 'js' / 'questions_data.js'
MD_DIR     = SCRIPT_DIR.parent / '詳解'
HEADER_RE  = re.compile(r'【(\d+)\s*年[^】]{0,30}?第\s*(\d+)\s*題[^】]*?】')

def load_qdb():
    text = QDB_JS.read_text(encoding='utf-8').strip()
    text = text.removeprefix('window.QDB = ').rstrip(';\n')
    return json.loads(text)

def clean_text(text):
    # 僅保留中文字與英文字母，忽略標點、空白及數字，取前 20 個字比對
    text = "".join(c for c in text if ('\u4e00' <= c <= '\u9fff') or c.isalpha())
    return text

def align_file(file_path, qdb_questions):
    content = file_path.read_text(encoding='utf-8')
    if not content.strip():
        return
        
    matches = list(HEADER_RE.finditer(content))
    if not matches:
        return

    # 依大科分類（如 constitutional、commercial）進行全量比對，防範分類器誤差
    subj_code = SUBJECT_TO_SUBJ.get(file_path.stem)
    if not subj_code:
        return
    correct_qs = [q for q in qdb_questions if q.get('subject') == subj_code]
    
    # 建立「題幹特徵 -> 候選題目列表」對應表
    correct_lookup = {}
    for q in correct_qs:
        clean_q = clean_text(q['question'])
        if len(clean_q) >= 15:
            # 建立 15 字與 20 字的特徵，方便比對
            for length in [15, 20]:
                feature = clean_q[:length]
                if feature not in correct_lookup:
                    correct_lookup[feature] = []
                correct_lookup[feature].append(q)

    preamble = content[:matches[0].start()]
    blocks = []
    corrected_count = 0
    warning_count = 0

    for i, m in enumerate(matches):
        orig_year = int(m.group(1))
        orig_num  = int(m.group(2))
        orig_header = m.group(0)
        
        block_start = m.start()
        block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block_content = content[block_start:block_end].strip()
        
        # 排除標頭，並按行分析以跳過中繼資料 (例如重要度、難度、# 標籤等)
        content_after_header = block_content[len(orig_header):].strip()
        lines = content_after_header.splitlines()
        q_stem_raw = ""
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            # 跳過元數據行
            if any(line_str.startswith(prefix) for prefix in ['重要度', '難度', '單選題', '選擇題', '考點', '單選', '★', '▲', '■', '●', '⭐', '🔥', '📌', '#']):
                continue
            q_stem_raw = line_str
            break
            
        # 如果整段為空，直接保留
        if not q_stem_raw:
            blocks.append(block_content)
            continue
            
        clean_stem = clean_text(q_stem_raw)
        
        # 尋找匹配
        candidates = []
        for length in [20, 15]:
            feature = clean_stem[:length]
            if len(feature) >= length and feature in correct_lookup:
                candidates = correct_lookup[feature]
                break
                
        if candidates:
            # 優先選擇年份相同的候選題 (避免公物題等多題重複造成的誤判)
            matched_q = None
            for cand in candidates:
                if cand['year'] == orig_year:
                    matched_q = cand
                    break
            # 如果年份不同，再嘗試找題號相同的候選題
            if not matched_q:
                for cand in candidates:
                    if cand['num'] == orig_num:
                        matched_q = cand
                        break
            # 真的不行就取第一個
            if not matched_q:
                matched_q = candidates[0]
                
            real_year = matched_q['year']
            real_num  = matched_q['num']
            
            if real_year != orig_year or real_num != orig_num:
                new_header = f"【{real_year}年 第{real_num}題】"
                block_content = new_header + block_content[len(orig_header):]
                corrected_count += 1
                print(f"  [修正] {file_path.name}: 原 {orig_header} -> 修正為 {new_header}")
        else:
            warning_count += 1
            print(f"  [警告] {file_path.name}: {orig_header} 找不到匹配題幹！(題幹開頭: {q_stem_raw[:30]}...)")
            
        blocks.append(block_content)

    # 重新拼接並寫回
    new_content = preamble + "\n\n".join(blocks) + "\n"
    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [完成] {file_path.name}: 共比對 {len(matches)} 題，自動修正 {corrected_count} 題，警告 {warning_count} 題。")

def main():
    print("開始自動校對與對齊詳解標題...")
    qdb = load_qdb()
    for filepath in sorted(MD_DIR.glob('*.md')):
        align_file(filepath, qdb['questions'])
    print("所有檔案校對完成！")

if __name__ == '__main__':
    main()
