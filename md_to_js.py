#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_to_js.py
解析 ../詳解/*.md → js/explanations_data.js

執行方式：
  python md_to_js.py
"""
import re, json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MD_DIR     = SCRIPT_DIR.parent / '詳解'
OUT_JS     = SCRIPT_DIR / 'js' / 'explanations_data.js'

# 科目名稱 → question id 中的 subj 碼
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

# 題目標頭：【114年 第1題】 或 【114 年 第 1 題】 等各種空格變體
HEADER_RE = re.compile(r'【(\d+)\s*年[^】]{0,30}?第\s*(\d+)\s*題[^】]*?】')

# 停止關鍵字（在選項文本中遇到時截斷）
STOP_KEYWORDS = ['法律依據', '核心概念', '補充提醒']


def clean_text(s):
    """去除多餘空行，合併換行"""
    lines = [l.strip() for l in s.split('\n')]
    # 過濾掉 --- 分隔線和空行
    out = []
    for l in lines:
        if re.match(r'^-+$', l):
            continue
        out.append(l)
    return '\n'.join(out).strip()


def extract_options(analysis_text):
    """
    從分析段落中抽取 (A)(B)(C)(D) 各選項解析。
    支援以下格式：
      (A) 錯誤：...
      (A) 正確：...
      A)、(B)、(C) 錯誤：...   ← 保險法特殊格式
    """
    options = {}

    # 先移除 核心概念/法律依據/補充提醒 段落，避免干擾選項切割
    cut = len(analysis_text)
    for kw in STOP_KEYWORDS:
        m = re.search(r'\n' + kw + r'[：:]', analysis_text)
        if m and m.start() < cut:
            cut = m.start()
    text = analysis_text[:cut]

    # ── 處理 (A)/(B)/(C)/(D) 開頭的選項 ──────────────────────────
    # 在「行首」出現 (X) 的地方切割
    segments = re.split(r'\n(?=[ \t]*\([ABCD]\))', '\n' + text)
    for seg in segments:
        seg = seg.strip()
        # 處理合併選項 (A) (B)(C)❌ 均錯誤。 或 (A)(B)(C) 均正確 等
        combined_header = re.match(r'^(\([ABCD]\)\s*)+(?:[✅❌]\s*)?(?:均)?(?:正確|錯誤)', seg)
        if combined_header:
            letters_combined = re.findall(r'\(([ABCD])\)', combined_header.group(0))
            rest_combined = seg[combined_header.end():]
            rest_combined = re.sub(r'^[。:：]\s*', '', rest_combined)
            content_combined = ' '.join(l.strip() for l in rest_combined.split('\n') if l.strip())
            for lc in letters_combined:
                if lc not in options and content_combined:
                    options[lc] = {'label': '', 'reason': content_combined}
            continue

        m = re.match(r'\(([ABCD])\)\s*([\s\S]*)', seg)
        if not m:
            continue
        letter  = m.group(1)
        content = m.group(2).strip()
        # 去除 ✅/❌ 和 正確：/錯誤：/正確。/錯誤。 前綴
        content = re.sub(r'^[✅❌]\s*', '', content)
        content = re.sub(r'^(?:正確|錯誤)[：:。]\s*', '', content)
        # 只取截至下個段落的文字，合成一行
        content = ' '.join(l.strip() for l in content.split('\n') if l.strip())
        if content:
            options[letter] = {'label': '', 'reason': content}

    # ── 處理 A)、(B)、(C) 合併寫法（保險法等） ───────────────────
    for m in re.finditer(
        r'^([ABCD])\)(?:[、，]\([ABCD]\))*\s*(?:正確|錯誤)[：:]\s*([\s\S]*?)(?=\n[ABCD]\)|\n\([ABCD]\)|\Z)',
        text, re.MULTILINE
    ):
        letters = [m.group(1)] + re.findall(r'\(([ABCD])\)', m.group(0).split('：')[0].split(':')[0])
        reason_raw = ' '.join(l.strip() for l in m.group(2).split('\n') if l.strip())
        reason = re.sub(r'^(?:正確|錯誤)[：:。]\s*', '', reason_raw)
        for letter in set(letters):
            if letter not in options:  # 不覆蓋已有解析
                options[letter] = {'label': '', 'reason': reason}

    return options


def parse_block(block):
    """解析單一題目段落"""
    block = block.strip()
    if not block:
        return None

    # ── 正確答案 ──────────────────────────────────────────────────
    m = re.search(r'正確答案[：:]\s*([ABCD])', block)
    correct = m.group(1) if m else ''

    # ── 找到分析段落（優先抓 逐項分析 之後，否則用整個 block） ──
    analysis_text = block
    m2 = re.search(r'逐項分析[：:]?\s*\n+([\s\S]+)', block)
    if m2:
        analysis_text = m2.group(1)
    else:
        # Format A（刑法等）：選項直接跟在 正確答案 之後
        m3 = re.search(r'正確答案[：:]\s*[ABCD][^\n]*\n+([\s\S]+)', block)
        if m3:
            analysis_text = m3.group(1)
        # Format 詳解格式：選項跟在 詳解：之後
        else:
            m4 = re.search(r'詳解[：:]\s*\n+([\s\S]+)', block)
            if m4:
                analysis_text = m4.group(1)

    # ── 選項解析 ────────────────────────────────────────────────
    options = extract_options(analysis_text)

    # ── 核心概念 ────────────────────────────────────────────────
    concept = ''
    m_c = re.search(r'核心概念[：:]\s*([\s\S]*?)(?=\n\n|\n補充提醒|\n法律依據|\n---|\Z)', block)
    if m_c:
        raw = m_c.group(1).strip()
        # 移除嵌入的補充提醒（部分檔案會在同一行繼續寫）
        raw = re.sub(r'\s*⚠️?\s*補充提醒[：:][\s\S]*', '', raw).strip()
        concept = raw

    # ── 補充提醒 ────────────────────────────────────────────────
    supplement = ''
    # 1. 顯式 補充提醒：...
    m_s = re.search(r'(?:⚠️\s*)?補充提醒[：:]\s*([\s\S]*?)(?=\n\n|\n---|\n法律依據|\Z)', block)
    if m_s:
        s = m_s.group(1).strip()
        if s and not re.match(r'^-+$', s) and s.lower() != '無' and s != '撰寫':
            supplement = s
    # 2. 嵌在核心概念行尾的補充提醒
    if not supplement:
        m_c2 = re.search(r'⚠️\s*補充提醒[：:]\s*([\s\S]*?)(?=\n---|\n\n|\Z)', block)
        if m_c2:
            s2 = m_c2.group(1).strip()
            if s2:
                supplement = s2

    # ── 法律依據 ────────────────────────────────────────────────
    law_basis = ''
    m_l = re.search(r'法律依據[：:]\s*(.+)', block)
    if m_l:
        # 只取第一行（citation），避免複製全文
        law_basis = m_l.group(1).strip().split('\n')[0].strip()

    # 若選項或概念都沒有，跳過
    if not options and not concept:
        return None

    return {
        'options':    options,
        'concept':    concept,
        'law_basis':  law_basis,
        'supplement': supplement,
    }


def parse_md(filepath, subj):
    """解析單一 MD 檔，回傳 {question_id: explanation_dict}"""
    content = filepath.read_text(encoding='utf-8')
    if not content.strip():
        return {}

    headers = list(HEADER_RE.finditer(content))
    if not headers:
        print(f'  [WARN] {filepath.name}: 找不到題目標頭，跳過')
        return {}

    results = {}
    for i, hdr in enumerate(headers):
        year = int(hdr.group(1))
        num  = int(hdr.group(2))
        qid  = f'{year}_{subj}_{num}'

        block_start = hdr.end()
        block_end   = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block       = content[block_start:block_end]

        expl = parse_block(block)
        if expl:
            results[qid] = expl

    return results


def load_existing():
    """載入現有 explanations_data.js 中的資料（AI 批次生成）"""
    if not OUT_JS.exists():
        return {}
    try:
        text = OUT_JS.read_text(encoding='utf-8').strip()
        m = re.search(r'Object\.assign\(window\.EXPLANATIONS,\s*(\{[\s\S]*\})\s*\)', text)
        if m:
            return json.loads(m.group(1))
    except Exception as e:
        print(f'[WARN] 無法解析現有 JS：{e}')
    return {}


def main():
    # 以現有 AI 批次資料為底層
    all_expl = load_existing()
    print(f'現有詳解條目：{len(all_expl)} 筆')

    total_new = 0
    for md_file in sorted(MD_DIR.glob('*.md')):
        subj = SUBJECT_TO_SUBJ.get(md_file.stem)
        if subj is None:
            print(f'  [SKIP] {md_file.name}（未知科目）')
            continue

        parsed = parse_md(md_file, subj)
        print(f'  {md_file.name}: 解析 {len(parsed)} 題')
        total_new += len(parsed)
        all_expl.update(parsed)   # MD 資料優先，覆蓋 AI 批次資料

    print(f'\n總計解析新詳解：{total_new} 筆，合計：{len(all_expl)} 筆')

    # ── 輸出 JS ────────────────────────────────────────────────
    header = (
        '// 詳解資料 — 由 md_to_js.py 自動產生（含人工詳解MD + AI批次資料）\n'
        '// 請勿手動修改，如需覆寫請編輯 ../詳解/*.md 後重新執行 md_to_js.py\n'
    )
    js_body = json.dumps(all_expl, ensure_ascii=False, indent=2)

    OUT_JS.write_text(
        header +
        'window.EXPLANATIONS = window.EXPLANATIONS || {};\n'
        'Object.assign(window.EXPLANATIONS, \n' +
        js_body + '\n);\n',
        encoding='utf-8'
    )
    print(f'已輸出 → {OUT_JS}')


if __name__ == '__main__':
    main()
