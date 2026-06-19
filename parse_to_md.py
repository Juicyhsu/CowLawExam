import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QDB_JS = SCRIPT_DIR / 'js' / 'questions_data.js'
OUTPUT_DIR = SCRIPT_DIR.parent / '詳解'

def get_stars(val):
    # val is typically 1 to 5. Map it to 1 to 3 stars.
    if val >= 4:
        return "⭐⭐⭐"
    elif val == 3:
        return "⭐⭐"
    else:
        return "⭐"

def get_fires(val):
    # Map difficulty (typically 1 to 5) to 1 to 3 fires.
    if val >= 4:
        return "🔥🔥🔥"
    elif val == 3:
        return "🔥🔥"
    else:
        return "🔥"

def main():
    if not QDB_JS.exists():
        print(f"Error: {QDB_JS} not found", file=sys.stderr)
        sys.exit(1)

    text = QDB_JS.read_text(encoding='utf-8').strip()
    if text.startswith('window.QDB = '):
        text = text[len('window.QDB = '):]
    if text.endswith(';'):
        text = text[:-1]
    
    qdb = json.loads(text)
    questions = qdb['questions']

    # Get subject from command line arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', required=True, help='Chinese subject name, e.g. 證券交易法')
    args = parser.parse_args()

    sub_questions = [q for q in questions if q.get('law_subject') == args.subject]
    if not sub_questions:
        print(f"No questions found for subject: {args.subject}", file=sys.stderr)
        sys.exit(1)

    # Group by year, then sort by question number
    grouped = {}
    for q in sub_questions:
        grouped.setdefault(q['year'], []).append(q)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_file = OUTPUT_DIR / f"{args.subject}.md"

    lines = []
    lines.append(f"# {args.subject} 歷屆一試詳解\n")

    for year in sorted(grouped.keys(), reverse=True):
        lines.append(f"## {year}年")
        # Sort questions in this year by num
        sorted_qs = sorted(grouped[year], key=lambda x: x['num'])
        for q in sorted_qs:
            stars = get_stars(q.get('importance', 3))
            fires = get_fires(q.get('difficulty', 3))
            opts = q.get('options', {})
            
            lines.append(f"### 【{q['year']}年 第{q['num']}題】")
            lines.append(f"重要度：{stars} ｜ 難度：{fires}")
            lines.append(q['question'].strip())
            lines.append("")
            lines.append(f"(A) {opts.get('A', '').strip()}")
            lines.append("")
            lines.append(f"(B) {opts.get('B', '').strip()}")
            lines.append("")
            lines.append(f"(C) {opts.get('C', '').strip()}")
            lines.append("")
            lines.append(f"(D) {opts.get('D', '').strip()}")
            lines.append("📝 詳解")
            lines.append("")
            lines.append(f"✔ 正確答案：({q['answer']})")
            lines.append(f"【(A)】❌ 錯誤")
            lines.append("理由：")
            lines.append(f"【(B)】❌ 錯誤")
            lines.append("理由：")
            lines.append(f"【(C)】❌ 錯誤")
            lines.append("理由：")
            lines.append(f"【(D)】❌ 錯誤")
            lines.append("理由：")
            lines.append("🔑 核心概念： ")
            lines.append("⚠️ 補充提醒： ")
            lines.append("")
            lines.append("---")
            lines.append("")

    out_file.write_text("\n".join(lines), encoding='utf-8')
    print(f"Generated template for {args.subject} in {out_file} ({len(sub_questions)} questions)")

if __name__ == '__main__':
    main()
