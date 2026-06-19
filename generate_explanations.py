#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
律師國考批次生成詳解
用法：
  python generate_explanations.py                    # 全部題目（free tier 速率）
  python generate_explanations.py --mode paid        # paid tier（較快）
  python generate_explanations.py --subject 刑法     # 只跑特定科目
  python generate_explanations.py --limit 10        # 只跑前 N 題（測試用）
  python generate_explanations.py --no-search       # 停用 Google Search（純靠訓練資料）
中斷後再執行會自動從上次進度繼續。
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR   = Path(__file__).parent
QDB_JS       = SCRIPT_DIR / 'js' / 'questions_data.js'
PROGRESS_FILE = SCRIPT_DIR / 'explanation_progress.json'
OUTPUT_JS    = SCRIPT_DIR / 'js' / 'explanations_data.js'

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL   = 'gemini-2.5-flash'
GEMINI_URL     = (
    f'https://generativelanguage.googleapis.com/v1beta/models/'
    f'{GEMINI_MODEL}:generateContent'
)

SYSTEM_INSTRUCTION = (
    '你是台灣律師一試（第一試）的命題與解題專家，精通中華民國各法律。'
    '回答時請使用繁體中文。'
    '如需引用大法官釋字號碼、憲法法庭裁判字號或重要判決，'
    '請先透過 Google 搜尋確認正確資料再引用，切勿憑記憶猜測號碼。'
)

PROMPT_TEMPLATE = """\
請為以下律師一試題目生成詳解，並以 JSON 格式回傳（只輸出 JSON，不要任何前言或說明文字）。

【題目】{year}年 {law_subject} 第{num}題
{question}
(A) {A}
(B) {B}
(C) {C}
(D) {D}
正確答案：({answer})

【詳解格式要求】
- options：每個選項必須有 label（"正確——一句話" 或 "錯誤——一句話"）和 reason（詳細理由 1–3 句，引用法條含條次，如刑法§15I）
- concept：一行點出本題考點（20字內）
- law_basis：備註相關法條條次清單（純文字）
- supplement：有易混淆考點或近年修法時填寫，否則填空字串 ""

【必須回傳的 JSON 格式】
{{
  "options": {{
    "A": {{"label": "正確/錯誤——一句話說明", "reason": "詳細理由"}},
    "B": {{"label": "...", "reason": "..."}},
    "C": {{"label": "...", "reason": "..."}},
    "D": {{"label": "...", "reason": "..."}}
  }},
  "concept": "一行核心概念",
  "law_basis": "刑法§XX、§YY",
  "supplement": ""
}}"""


def load_questions():
    text = QDB_JS.read_text(encoding='utf-8')
    # strip "window.QDB = " prefix and trailing ";"
    text = text.strip()
    if text.startswith('window.QDB = '):
        text = text[len('window.QDB = '):]
    if text.endswith(';'):
        text = text[:-1]
    qdb = json.loads(text)
    return qdb['questions']


def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
    return {}


def save_progress(progress):
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def extract_json(text):
    """從 Gemini 回應中提取 JSON。先嘗試直接 parse，再用 regex 找 {}。"""
    text = text.strip()
    # 移除可能的 markdown code fence
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 找最外層 {...}
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def call_gemini(prompt, use_search=True, retry=0):
    """呼叫 Gemini API，回傳解析後的 JSON dict 或 None。"""
    payload = {
        'system_instruction': {'parts': [{'text': SYSTEM_INSTRUCTION}]},
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 1800,
        }
    }
    if use_search:
        payload['tools'] = [{'googleSearch': {}}]

    try:
        resp = requests.post(
            f'{GEMINI_URL}?key={GEMINI_API_KEY}',
            json=payload,
            timeout=45
        )
        if resp.status_code == 429:
            wait = 65  # 等一分鐘讓配額重置
            print(f'    速率限制，等待 {wait}s…', flush=True)
            time.sleep(wait)
            if retry < 2:
                return call_gemini(prompt, use_search, retry + 1)
            return None
        if resp.status_code in (500, 502, 503):
            if retry < 2:
                time.sleep(10)
                return call_gemini(prompt, use_search, retry + 1)
            return None
        resp.raise_for_status()

        candidates = resp.json().get('candidates', [])
        if not candidates:
            return None
        raw_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        result = extract_json(raw_text)

        # 若使用 grounding 但 JSON 解析失敗，不帶 search 重試
        if result is None and use_search and retry == 0:
            print('    grounding 回應無法解析 JSON，改用標準模式重試…', flush=True)
            return call_gemini(prompt, use_search=False, retry=0)

        return result

    except requests.Timeout:
        if retry < 2:
            time.sleep(15)
            return call_gemini(prompt, use_search, retry + 1)
        return None
    except Exception as e:
        print(f'    API 錯誤：{e}', flush=True)
        return None


def validate_explanation(data):
    """確認回傳結構完整。"""
    if not isinstance(data, dict):
        return False
    opts = data.get('options', {})
    if not isinstance(opts, dict):
        return False
    for key in ('A', 'B', 'C', 'D'):
        if key not in opts:
            return False
        if not isinstance(opts[key], dict):
            return False
        if 'label' not in opts[key] or 'reason' not in opts[key]:
            return False
    return 'concept' in data and 'law_basis' in data


def write_output(progress):
    """將 progress dict 輸出為 js/explanations_data.js。"""
    lines = [
        '// 批次生成的詳解資料 — 由 generate_explanations.py 自動產生，請勿手動修改',
        '// 手動詳解請寫在 js/flashcards.js（優先級高於本檔）',
        'window.EXPLANATIONS = window.EXPLANATIONS || {};',
        'Object.assign(window.EXPLANATIONS, ',
    ]
    lines.append(json.dumps(progress, ensure_ascii=False, indent=2))
    lines.append(');')
    OUTPUT_JS.write_text('\n'.join(lines), encoding='utf-8')
    print(f'\n已輸出 {OUTPUT_JS}（{len(progress)} 題）')


def main():
    parser = argparse.ArgumentParser(description='批次生成律師國考詳解')
    parser.add_argument('--mode', choices=['free', 'paid'], default='free',
                        help='free=15 RPM(預設), paid=60 RPM')
    parser.add_argument('--subject', default='',
                        help='只處理特定科目，如：刑法、民法、憲法')
    parser.add_argument('--limit', type=int, default=0,
                        help='只處理前 N 題（測試用）')
    parser.add_argument('--no-search', action='store_true',
                        help='停用 Google Search grounding')
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print('錯誤：請在 .env 設定 GEMINI_API_KEY', file=sys.stderr)
        sys.exit(1)

    sleep_sec = 1.0 if args.mode == 'paid' else 4.0
    use_search = not args.no_search

    print('載入題目…')
    questions = load_questions()
    if args.subject:
        questions = [q for q in questions if q.get('law_subject') == args.subject]
        print(f'篩選「{args.subject}」：{len(questions)} 題')
    if args.limit:
        questions = questions[:args.limit]
        print(f'限制前 {args.limit} 題')

    progress = load_progress()
    already  = sum(1 for q in questions if q['id'] in progress)
    todo     = [q for q in questions if q['id'] not in progress]

    print(f'總計 {len(questions)} 題，已完成 {already} 題，待處理 {len(todo)} 題')
    print(f'模式：{args.mode}（sleep={sleep_sec}s），Google Search：{"開啟" if use_search else "關閉"}')
    if not todo:
        print('全部完成！輸出 JS…')
        write_output({q["id"]: progress[q["id"]] for q in questions if q["id"] in progress})
        return

    flush_every = 10
    done_count  = 0
    fail_count  = 0

    for i, q in enumerate(todo):
        opts = q['options']
        prompt = PROMPT_TEMPLATE.format(
            year=q['year'],
            law_subject=q['law_subject'],
            num=q['num'],
            question=q['question'],
            A=opts.get('A', ''),
            B=opts.get('B', ''),
            C=opts.get('C', ''),
            D=opts.get('D', ''),
            answer=q['answer'],
        )

        print(f'[{already + i + 1}/{len(questions)}] {q["id"]}…', end=' ', flush=True)
        result = call_gemini(prompt, use_search=use_search)

        if result and validate_explanation(result):
            result['supplement'] = result.get('supplement', '')
            progress[q['id']] = result
            done_count += 1
            print('OK', flush=True)
        else:
            fail_count += 1
            print('FAIL（跳過）', flush=True)

        if (i + 1) % flush_every == 0:
            save_progress(progress)
            print(f'  進度已儲存（{already + i + 1} 題）', flush=True)

        time.sleep(sleep_sec)

    save_progress(progress)

    # 只輸出有完成的題目（整個 questions_data.js 的題目都含括）
    all_questions = load_questions()
    full_progress = load_progress()
    output_data = {q['id']: full_progress[q['id']] for q in all_questions if q['id'] in full_progress}
    write_output(output_data)

    print(f'\n完成！成功 {done_count} 題，失敗 {fail_count} 題')
    if fail_count:
        print('重新執行此腳本可自動補跑失敗題目。')


if __name__ == '__main__':
    main()
