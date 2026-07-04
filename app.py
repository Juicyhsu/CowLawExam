"""
律師國考刷題系統 ── Flask 後端
功能：靜態檔案伺服 + 帳號系統 + 進度同步 + Gemini AI 代理
"""
import os, sqlite3, time, json
from datetime import datetime, timedelta, timezone
from functools import wraps

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = BASE_DIR   # 靜態檔直接從本機磁碟伺服

# 資料目錄（Volume 持久化）
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

import bcrypt
import jwt
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=None)   # 停用內建 static，改用下方自訂路由（支援 gzip）
CORS(app, supports_credentials=True)

SECRET_KEY    = os.getenv('SECRET_KEY', 'dev-only-do-not-use-in-production-please-set-env-32')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
DB_PATH       = os.path.join(DATA_DIR, 'progress.db')

# ── 每用戶 AI 問答速率限制 ─────────────────────────
_rate = {}   # {user_id: [timestamps]}
RATE_LIMIT = 15   # 每分鐘最多次數

def check_rate(user_id):
    now = time.time()
    ts = [t for t in _rate.get(user_id, []) if now - t < 60]
    if len(ts) >= RATE_LIMIT:
        return False
    ts.append(now)
    _rate[user_id] = ts
    return True

# ── 資料庫 ────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS progress (
                user_id     INTEGER NOT NULL,
                question_id TEXT    NOT NULL,
                choice      TEXT    NOT NULL,
                is_correct  INTEGER NOT NULL,
                answered_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS reviewed_concepts (
                user_id     INTEGER NOT NULL,
                concept_id  TEXT    NOT NULL,
                reviewed_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, concept_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS user_audio_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                note_key    TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                points_json TEXT    NOT NULL DEFAULT '[]',
                updated_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, note_key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
                user_id       INTEGER NOT NULL,
                question_id   TEXT    NOT NULL,
                bookmarked_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS question_notes (
                user_id     INTEGER NOT NULL,
                question_id TEXT    NOT NULL,
                note_text   TEXT    NOT NULL DEFAULT '',
                updated_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS user_concept_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                note_key    TEXT    NOT NULL,
                subject     TEXT    NOT NULL DEFAULT '',
                topic_id    TEXT    NOT NULL DEFAULT '',
                front       TEXT    NOT NULL DEFAULT '',
                back        TEXT    NOT NULL DEFAULT '',
                updated_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, note_key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id       INTEGER PRIMARY KEY,
                settings_json TEXT    NOT NULL DEFAULT '{}',
                updated_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

init_db()

# ── JWT 工具 ──────────────────────────────────────
def make_token(user_id: int) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': '請先登入'}), 401
        token = auth[7:]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '登入已過期，請重新登入'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': '無效的驗證憑證'}), 401
        return f(payload['user_id'], *args, **kwargs)
    return decorated

# ── API Routes ────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not email or '@' not in email:
        return jsonify({'error': '請輸入有效的 Email'}), 400
    if len(password) < 6:
        return jsonify({'error': '密碼至少需要 6 個字元'}), 400
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with get_db() as conn:
            cur = conn.execute(
                'INSERT INTO users (email, password_hash) VALUES (?, ?)',
                (email, pw_hash)
            )
            uid = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({'error': '此 Email 已被註冊'}), 409
    return jsonify({'token': make_token(uid), 'email': email}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    with get_db() as conn:
        row = conn.execute(
            'SELECT id, password_hash FROM users WHERE email = ?', (email,)
        ).fetchone()
    if not row or not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Email 或密碼錯誤'}), 401
    return jsonify({'token': make_token(row['id']), 'email': email})

@app.route('/api/me', methods=['GET'])
@require_auth
def me(user_id):
    with get_db() as conn:
        row = conn.execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()
    return jsonify({'email': row['email'], 'user_id': user_id})

# ── 進度 ─────────────────────────────────────────
@app.route('/api/progress', methods=['GET'])
@require_auth
def get_progress(user_id):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT question_id, choice, is_correct FROM progress WHERE user_id = ?',
            (user_id,)
        ).fetchall()
        concepts = conn.execute(
            'SELECT concept_id FROM reviewed_concepts WHERE user_id = ?',
            (user_id,)
        ).fetchall()
    answers = {r['question_id']: {'choice': r['choice'], 'correct': bool(r['is_correct'])} for r in rows}
    reviewed = [r['concept_id'] for r in concepts]
    return jsonify({'answers': answers, 'reviewed_concepts': reviewed})

@app.route('/api/progress', methods=['DELETE'])
@require_auth
def clear_progress(user_id):
    data = request.json or {}
    question_ids = data.get('question_ids')   # 若有傳 list，只刪指定題目
    with get_db() as conn:
        if question_ids:
            placeholders = ','.join('?' * len(question_ids))
            conn.execute(
                f'DELETE FROM progress WHERE user_id = ? AND question_id IN ({placeholders})',
                [user_id] + list(question_ids)
            )
            # reviewed_concepts 為主題 key，不按題號刪除，分科清除時不動它
        else:
            conn.execute('DELETE FROM progress WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM reviewed_concepts WHERE user_id = ?', (user_id,))
    return jsonify({'ok': True})

@app.route('/api/progress', methods=['POST'])
@require_auth
def save_progress(user_id):
    data = request.json or {}
    answers  = data.get('answers', {})
    reviewed = data.get('reviewed_concepts', [])
    with get_db() as conn:
        for qid, rec in answers.items():
            conn.execute(
                'INSERT OR REPLACE INTO progress (user_id, question_id, choice, is_correct) VALUES (?,?,?,?)',
                (user_id, qid, rec.get('choice', ''), int(rec.get('correct', False)))
            )
        for cid in reviewed:
            conn.execute(
                'INSERT OR IGNORE INTO reviewed_concepts (user_id, concept_id) VALUES (?,?)',
                (user_id, cid)
            )
    return jsonify({'ok': True})

# ── 聽讀自訂筆記 ─────────────────────────────────
@app.route('/api/audio_notes', methods=['GET'])
@require_auth
def get_audio_notes(user_id):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT note_key, title, points_json FROM user_audio_notes WHERE user_id = ?',
            (user_id,)
        ).fetchall()
    return jsonify({r['note_key']: {'title': r['title'], 'points': json.loads(r['points_json'])} for r in rows})

@app.route('/api/audio_notes', methods=['POST'])
@require_auth
def save_audio_note(user_id):
    data     = request.json or {}
    note_key = (data.get('note_key') or '').strip()
    title    = (data.get('title')    or '').strip()
    points   = data.get('points', [])
    if not note_key or not title:
        return jsonify({'error': '缺少必要欄位'}), 400
    with get_db() as conn:
        conn.execute(
            '''INSERT OR REPLACE INTO user_audio_notes
               (user_id, note_key, title, points_json, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (user_id, note_key, title, json.dumps(points, ensure_ascii=False))
        )
    return jsonify({'ok': True})

@app.route('/api/audio_notes/<path:note_key>', methods=['DELETE'])
@require_auth
def delete_audio_note(user_id, note_key):
    with get_db() as conn:
        conn.execute(
            'DELETE FROM user_audio_notes WHERE user_id = ? AND note_key = ?',
            (user_id, note_key)
        )
    return jsonify({'ok': True})

# ── 書籤（星號收藏） ──────────────────────────────
@app.route('/api/bookmarks', methods=['GET'])
@require_auth
def get_bookmarks(user_id):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT question_id FROM bookmarks WHERE user_id = ?', (user_id,)
        ).fetchall()
    return jsonify([r['question_id'] for r in rows])

@app.route('/api/bookmarks', methods=['POST'])
@require_auth
def toggle_bookmark(user_id):
    data = request.json or {}
    qid  = (data.get('question_id') or '').strip()
    if not qid:
        return jsonify({'error': '缺少 question_id'}), 400
    with get_db() as conn:
        exists = conn.execute(
            'SELECT 1 FROM bookmarks WHERE user_id=? AND question_id=?', (user_id, qid)
        ).fetchone()
        if exists:
            conn.execute('DELETE FROM bookmarks WHERE user_id=? AND question_id=?', (user_id, qid))
            return jsonify({'bookmarked': False})
        else:
            conn.execute('INSERT OR IGNORE INTO bookmarks (user_id, question_id) VALUES (?,?)', (user_id, qid))
            return jsonify({'bookmarked': True})

# ── 題目筆記 ─────────────────────────────────────
@app.route('/api/question_notes', methods=['GET'])
@require_auth
def get_question_notes(user_id):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT question_id, note_text FROM question_notes WHERE user_id = ?', (user_id,)
        ).fetchall()
    return jsonify({r['question_id']: r['note_text'] for r in rows})

@app.route('/api/question_notes', methods=['POST'])
@require_auth
def save_question_note(user_id):
    data = request.json or {}
    qid  = (data.get('question_id') or '').strip()
    text = data.get('note_text', '')
    if not qid:
        return jsonify({'error': '缺少 question_id'}), 400
    with get_db() as conn:
        if text:
            conn.execute(
                '''INSERT OR REPLACE INTO question_notes (user_id, question_id, note_text, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)''',
                (user_id, qid, text)
            )
        else:
            conn.execute('DELETE FROM question_notes WHERE user_id=? AND question_id=?', (user_id, qid))
    return jsonify({'ok': True})

# ── 重點整理（概念）筆記 ─────────────────────────
@app.route('/api/concept_notes', methods=['GET'])
@require_auth
def get_concept_notes(user_id):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT note_key, subject, topic_id, front, back FROM user_concept_notes WHERE user_id = ?',
            (user_id,)
        ).fetchall()
    return jsonify({
        r['note_key']: {
            'subject': r['subject'], 'topic_id': r['topic_id'],
            'front': r['front'],     'back': r['back']
        } for r in rows
    })

@app.route('/api/concept_notes', methods=['POST'])
@require_auth
def save_concept_note(user_id):
    data     = request.json or {}
    note_key = (data.get('note_key') or '').strip()
    if not note_key:
        return jsonify({'error': '缺少 note_key'}), 400
    with get_db() as conn:
        conn.execute(
            '''INSERT OR REPLACE INTO user_concept_notes
               (user_id, note_key, subject, topic_id, front, back, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (user_id, note_key,
             data.get('subject',''), data.get('topic_id',''),
             data.get('front',''),   data.get('back',''))
        )
    return jsonify({'ok': True})

@app.route('/api/concept_notes/<path:note_key>', methods=['DELETE'])
@require_auth
def delete_concept_note(user_id, note_key):
    with get_db() as conn:
        conn.execute(
            'DELETE FROM user_concept_notes WHERE user_id=? AND note_key=?', (user_id, note_key)
        )
    return jsonify({'ok': True})

# ── 使用者設定（自訂科目等） ──────────────────────
@app.route('/api/user_settings', methods=['GET'])
@require_auth
def get_user_settings(user_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT settings_json FROM user_settings WHERE user_id=?', (user_id,)
        ).fetchone()
    return jsonify(json.loads(row['settings_json']) if row else {})

@app.route('/api/user_settings', methods=['POST'])
@require_auth
def save_user_settings(user_id):
    data = request.json or {}
    with get_db() as conn:
        conn.execute(
            '''INSERT OR REPLACE INTO user_settings (user_id, settings_json, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)''',
            (user_id, json.dumps(data, ensure_ascii=False))
        )
    return jsonify({'ok': True})

# ── Gemini AI 代理 ────────────────────────────────
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
SYSTEM_PROMPT = (
    '你是台灣律師一試的解題老師，精通台灣法律。請以繁體中文回答。'
    '【回答原則】'
    '1. 直接進入解析，不寫問候語、不重複題目內容。'
    '2. 只問某選項就只解釋該選項；問全部才逐項解析。'
    '3. 說明要精簡但完整：點出錯誤或正確的核心理由 + 關鍵法條（含條次）即可，'
    '   不需要把每個子概念都展開成獨立段落，能合併說明的就合併。'
    '4. 避免過多層級（減少大標題＋子標題＋子子標題的結構），'
    '   一到兩段連貫說明通常比四五個編號區塊更易讀。'
    '5. 大法官釋字或判決號碼不確定時，註明「需自行查證」。'
)

@app.route('/api/ask', methods=['POST'])
def ask_ai():
    if not GEMINI_API_KEY:
        return jsonify({'error': '尚未設定 Gemini API Key，請在 .env 填入 GEMINI_API_KEY'}), 503
    ip = request.remote_addr or 'unknown'
    if not check_rate(ip):
        return jsonify({'error': '請求過於頻繁，請稍後再試'}), 429

    data = request.json or {}
    question_ctx = data.get('question_context', '')
    user_q       = data.get('user_question', '').strip()
    if not user_q:
        return jsonify({'error': '請輸入問題'}), 400

    prompt = f'{SYSTEM_PROMPT}\n\n【題目情境】\n{question_ctx}\n\n【考生提問】\n{user_q}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.2,
            'maxOutputTokens': 8192,
            'thinkingConfig': {'thinkingBudget': 512}  # 少量思考(512)+大輸出空間
        }
    }
    try:
        resp = requests.post(
            f'{GEMINI_URL}?key={GEMINI_API_KEY}',
            json=payload, timeout=25
        )
        resp.raise_for_status()
        answer = resp.json()['candidates'][0]['content']['parts'][0]['text']
        return jsonify({'answer': answer})
    except requests.Timeout:
        return jsonify({'error': 'AI 回應逾時，請稍後再試'}), 504
    except Exception as e:
        return jsonify({'error': f'AI 服務暫時異常：{str(e)[:80]}'}), 502

# ── AI 整理文字（順文字） ────────────────────────
_NO_MD = '嚴禁使用任何 Markdown 符號（不要出現 **、*、#、`、--- 等），純文字輸出。'
REFINE_PROMPTS = {
    'audio_note'    : '你是專業的法律國考教師。請將以下筆記改寫成適合「純語音聆聽」的講稿。要求：1. 繁體中文，必須盡量使用精確的「法律專業用語」與「法條實務文字」，確保內容具備高度的國考專業性；2. 雖然使用法律語言，但句型必須是「語氣平順且邏輯連貫的完整句子」，絕對不可使用簡略的碎片化條列，確保聽覺上能輕易吸收；3. 適當使用逗號斷句，幫助語音朗讀時有自然的停頓；4. 「每行」輸出一句完整的概念（做為播放器分段的斷點），請分行呈現；5. 嚴禁出現「本件」、「本案」、「甲」、「乙」、「丙」、「丁」、「戊」、「己」、「庚」、「辛」、「壬」、「癸」等考題角色代稱或案件指涉用語；6. 內容應純粹敘述法律概念本身（構成要件、法律效果、學說爭點），不可帶入任何與特定題目相關的背景事實前提，若原始筆記含有案例事實，應僅擷取法律概念以抽象通則方式呈現。只輸出改寫後的講稿，絕對不要加上任何開場白或結語。' + _NO_MD,
    'concept_back'  : '你是專業的法律國考教師。請將以下內容整理成「概念卡片背面」的最佳複習排版。要求：1. 繁體中文，使用條列式（每一行以「• 」開頭）；2. 必須保留所有的「關鍵字」、「法條與實務見解字號」以及「爭點結論」，不可過度刪減導致失去考試價值；3. 邏輯層次分明，讓考生能一目了然。只輸出整理後的內容，絕對不要加上任何開場白或結語。' + _NO_MD,
    'question_note' : '你是專業的法律國考教師。請將以下考生的錯題筆記，重新梳理為高分覆盤筆記。要求：1. 繁體中文，使用條列式（每一行以「• 」開頭）；2. 結構化呈現「爭點 / 錯誤原因 / 正確結論與法源」；3. 語句精鍊但邏輯完整，幫助考生快速回憶盲點。只輸出整理後的內容，絕對不要加上任何開場白或結語。' + _NO_MD,
}

def _strip_markdown(s):
    """移除 AI 殘留的 Markdown 符號，保留純文字與條列。"""
    import re
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)   # **粗體**
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)\*', r'\1', s)  # *斜體*
    s = re.sub(r'^#{1,6}\s*', '', s, flags=re.M)     # # 標題
    s = re.sub(r'`+', '', s)                          # 反引號
    s = re.sub(r'^\s*[-_]{3,}\s*$', '', s, flags=re.M)  # 分隔線
    s = re.sub(r'^\s*\*\s+', '• ', s, flags=re.M)    # * 項目符號 → •
    return s.strip()

@app.route('/api/ai_refine', methods=['POST'])
def ai_refine():
    if not GEMINI_API_KEY:
        return jsonify({'error': '尚未設定 Gemini API Key'}), 503
    ip = request.remote_addr or 'unknown'
    if not check_rate(ip):
        return jsonify({'error': '請求過於頻繁，請稍後再試'}), 429
    data  = request.json or {}
    text  = (data.get('text') or '').strip()
    mode  = data.get('mode', 'audio_note')
    if not text:
        return jsonify({'error': '請輸入文字'}), 400
    sys_prompt = REFINE_PROMPTS.get(mode, REFINE_PROMPTS['audio_note'])
    prompt = f'{sys_prompt}\n\n【原始內容】\n{text}'
    # 動態輸出上限：整理是「重組」非「擴寫」，輸出長度約等於或略短於輸入。
    # 以輸入字元數估算 token（中文約 1 字 ≈ 1.3 token），給 1.5 倍餘裕，
    # 下限 4096（短輸入也夠用），上限 32768（gemini-2.5-flash 支援）。
    est_in_tokens = int(len(text) * 1.3)
    max_out = max(4096, min(int(est_in_tokens * 1.5), 32768))
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': max_out}
    }
    try:
        resp = requests.post(
            f'{GEMINI_URL}?key={GEMINI_API_KEY}',
            json=payload, timeout=30
        )
        resp.raise_for_status()
        body = resp.json()
        cands = body.get('candidates') or []
        if not cands:
            # 可能被安全機制攔截
            reason = (body.get('promptFeedback') or {}).get('blockReason', '')
            return jsonify({'error': f'AI 無法處理此內容{("（" + reason + "）") if reason else ""}'}), 502
        cand = cands[0]
        parts = (cand.get('content') or {}).get('parts') or []
        answer = ''.join(p.get('text', '') for p in parts).strip()
        if not answer:
            return jsonify({'error': 'AI 未產生內容，請再試一次'}), 502
        answer = _strip_markdown(answer)
        truncated = cand.get('finishReason') == 'MAX_TOKENS'
        return jsonify({'result': answer, 'truncated': truncated})
    except requests.Timeout:
        return jsonify({'error': 'AI 回應逾時，內容可能過長，請分段整理'}), 504
    except Exception as e:
        return jsonify({'error': f'AI 服務暫時異常：{str(e)[:80]}'}), 502

# ── 靜態檔案 ─────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    # 若有預壓縮 .gz 且瀏覽器支援 gzip，送壓縮版以加速傳輸
    # 由於 git 會打亂部署時的 mtime，我們只要確定 .gz 存在就直接送
    if path.endswith('.js') and 'gzip' in request.headers.get('Accept-Encoding', ''):
        gz_full = os.path.join(STATIC_DIR, path + '.gz')
        if os.path.isfile(gz_full):
            resp = send_file(gz_full, mimetype='application/javascript', conditional=True)
            resp.headers['Content-Encoding'] = 'gzip'
            resp.headers['Vary'] = 'Accept-Encoding'
            resp.cache_control.max_age = 604800
            resp.cache_control.public = True
            return resp
    resp = send_from_directory(STATIC_DIR, path)
    if path.startswith('js/') and path.endswith('.js'):
        resp.cache_control.max_age = 604800
        resp.cache_control.public = True
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, port=port, host='0.0.0.0')
