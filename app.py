"""
律師國考刷題系統 ── Flask 後端
功能：靜態檔案伺服 + 帳號系統 + 進度同步 + Gemini AI 代理
"""
import os, sqlite3, time
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, supports_credentials=True)

SECRET_KEY    = os.getenv('SECRET_KEY', 'dev-only-change-me')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
DB_PATH       = os.path.join(os.path.dirname(__file__), 'progress.db')

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

# ── Gemini AI 代理 ────────────────────────────────
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
SYSTEM_PROMPT = (
    '你是台灣律師國家考試（律師一試）的專業輔導老師，精通台灣法律。'
    '請以繁體中文完整回答，務必把每個選項都解析完畢再結束，引用正確法條（含條次）。'
    '回答格式：先說明正確答案，再逐項解析 (A)(B)(C)(D)，最後一句核心概念。'
    '若問題涉及大法官釋字或憲法法庭判決號碼，不確定時說明「需自行查證」。'
    '每項解析約 1～2 句，全文 400 字以內。'
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

# ── 靜態檔案 ─────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, port=port, host='0.0.0.0')
