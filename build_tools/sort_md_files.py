#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sort_md_files.py
物理排序 ../詳解/*.md 底下的題目：按年份由新到舊 (Year DESC)，題號由小到大 (Num ASC)
"""
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
MD_DIR     = SCRIPT_DIR.parent / '詳解'
HEADER_RE  = re.compile(r'【(\d+)\s*年[^】]{0,30}?第\s*(\d+)\s*題[^】]*?】')

def sort_file(file_path):
    content = file_path.read_text(encoding='utf-8')
    if not content.strip():
        return
        
    matches = list(HEADER_RE.finditer(content))
    if not matches:
        print(f"  [WARN] {file_path.name}: 找不到題目標頭，跳過")
        return
        
    # 取得前導文字 (Preamble)
    preamble = content[:matches[0].start()]
    
    blocks = []
    for i, m in enumerate(matches):
        year = int(m.group(1))
        num  = int(m.group(2))
        
        block_start = m.start()
        block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block_content = content[block_start:block_end].strip()
        
        blocks.append({
            'year': year,
            'num': num,
            'content': block_content
        })
        
    # 排序：年份由新到舊 (Year DESC)，題號由小到大 (Num ASC)
    blocks.sort(key=lambda x: (-x['year'], x['num']))
    
    # 重新拼接
    new_content = preamble
    for b in blocks:
        new_content += b['content'] + '\n\n'
        
    # 寫回檔案
    file_path.write_text(new_content.strip() + '\n', encoding='utf-8')
    print(f"  [SUCCESS] {file_path.name} 已排序，共 {len(blocks)} 題")

def main():
    print("開始物理排序詳解 MD 檔案...")
    for filepath in sorted(MD_DIR.glob('*.md')):
        sort_file(filepath)
    print("排序完成！")

if __name__ == '__main__':
    main()
