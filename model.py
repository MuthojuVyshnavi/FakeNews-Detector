import os
import re
import string
import sqlite3
import pickle
from collections import Counter
from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash


# ------------------ APP SETUP ------------------
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SECRET_KEY"] = "supersecret123"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ------------------ HOME ROUTE ------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------ LOAD MODEL ------------------
model      = pickle.load(open(os.path.join(BASE_DIR, "model.pkl"),      "rb"))
vectorizer = pickle.load(open(os.path.join(BASE_DIR, "vectorizer.pkl"), "rb"))
print("✅ Model loaded successfully")
print("✅ Vectorizer loaded successfully")
print("🔍 Model type:", type(model).__name__)
print("🔍 Has predict_proba:", hasattr(model, "predict_proba"))


# ------------------ DATABASE ------------------
DB_PATH = os.path.join(BASE_DIR, "users.db")

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")  # reduces 'database is locked' errors
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        result TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()


# ------------------ NLP HELPERS ------------------

STOPWORDS = {
    'a','an','the','and','or','but','in','on','at','to','for','of','with',
    'is','are','was','were','be','been','being','have','has','had','do',
    'does','did','will','would','could','should','may','might','shall',
    'this','that','these','those','i','we','you','he','she','they','it',
    'my','our','your','his','her','their','its','who','which','what',
    'how','when','where','why','as','by','from','up','about','into',
    'through','during','before','after','not','no','so','if','than',
    'then','there','here','all','each','every','both','few','more','most',
    'other','some','such','only','own','same','too','very','just','also',
    'can','now','any','because','while','new','said','says','say','us',
    'its','their','s','t','re','ve','ll','d','m'
}

POSITIVE_WORDS = {
    'confirmed','official','verified','reported','announced','published',
    'research','study','expert','scientist','evidence','data','fact',
    'approved','legitimate','authorized','genuine','credible','reliable',
    'transparent','accurate','proven','established','peer-reviewed'
}

NEGATIVE_WORDS = {
    'fake','hoax','rumor','unverified','clickbait','conspiracy','shocking',
    'secret','exclusive','bombshell','explosive','sensational','alarming',
    'breaking','urgent','warning','danger','scandal','cover-up','exposed',
    'hidden','suppressed','banned','censored','truth','they','want','know'
}

SENTIMENT_POS = {
    'good','great','excellent','positive','success','benefit','improve',
    'growth','hope','progress','achievement','support','help','strong',
    'effective','important','significant','historic','launch','new','plan'
}

SENTIMENT_NEG = {
    'bad','terrible','negative','fail','failure','crisis','disaster',
    'corrupt','fraud','illegal','danger','threat','attack','kill','die',
    'loss','collapse','scandal','riot','violence','war','conflict','arrest'
}


def clean_text(t):
    t = str(t).lower()
    t = re.sub(r'http\S+|www\S+', '', t)
    t = re.sub(r'\d+', '', t)
    t = t.translate(str.maketrans('', '', string.punctuation))
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def extract_keywords(text, top_n=8):
    """Extract meaningful keywords from text using word frequency."""
    cleaned = clean_text(text)
    words = [w for w in cleaned.split() if w not in STOPWORDS and len(w) > 3]
    if not words:
        return []
    freq = Counter(words)
    # Boost words that appear in our signal lists
    for w in freq:
        if w in POSITIVE_WORDS or w in NEGATIVE_WORDS:
            freq[w] *= 2
    top = [w for w, _ in freq.most_common(top_n)]
    return top


def analyze_sentiment(text):
    """Simple rule-based sentiment: Positive / Negative / Neutral."""
    words = set(clean_text(text).split())
    pos = len(words & SENTIMENT_POS)
    neg = len(words & SENTIMENT_NEG)
    if pos > neg:
        return "Positive 😊"
    elif neg > pos:
        return "Negative 😟"
    else:
        return "Neutral 😐"


def build_explanation(text, prediction, confidence, keywords):
    """Generate a human-readable explanation for the prediction."""
    words = set(clean_text(text).split())

    fake_signals  = list(words & NEGATIVE_WORDS)
    real_signals  = list(words & POSITIVE_WORDS)

    if prediction == 1:   # Real
        if real_signals:
            signal_str = ", ".join(f"'{w}'" for w in real_signals[:3])
            return (f"The text uses credible language patterns such as {signal_str}. "
                    f"The model considers this likely genuine news "
                    f"({confidence}% confidence).")
        else:
            return (f"The language, tone, and structure resemble credible reporting. "
                    f"The model classified this as real news with {confidence}% confidence. "
                    f"Always cross-check with reliable sources.")
    else:                  # Fake
        if fake_signals:
            signal_str = ", ".join(f"'{w}'" for w in fake_signals[:3])
            return (f"The text contains language patterns commonly associated with "
                    f"misinformation, including words like {signal_str}. "
                    f"The model flagged this with {confidence}% confidence.")
        else:
            return (f"The writing style, structure, and word choices closely match "
                    f"patterns the model has learned from fake news articles "
                    f"({confidence}% confidence). Consider verifying with a trusted source.")


# ------------------ AUTH HELPERS ------------------
def get_current_user():
    return session.get("user_id")


# ------------------ ROUTES ------------------

@app.route("/register", methods=["POST"])
def register():
    data     = request.json
    username = data.get("username")
    password = data.get("password")
    hashed   = generate_password_hash(password)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print("REGISTER ERROR:", e)
        conn.rollback()
        return jsonify({"success": False, "message": "Username already exists"}), 400
    finally:
        conn.close()


@app.route("/login", methods=["POST"])
def login():
    data     = request.json
    username = data.get("username")
    password = data.get("password")
    conn     = sqlite3.connect(DB_PATH, timeout=10)
    c        = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[1], password):
        session["user_id"] = user[0]
        return jsonify({"success": True, "username": username})
    return jsonify({"success": False, "message": "Invalid credentials"})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ------------------ ANALYZE ------------------

@app.route("/analyze", methods=["POST"])
def analyze():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    text = data.get("text") or data.get("url")

    if not text:
        return jsonify({"success": False, "message": "No text or URL provided"}), 400

    cleaned    = clean_text(text)
    vec        = vectorizer.transform([cleaned])
    prediction = model.predict(vec)[0]

    print("----- DEBUG -----")
    print("INPUT     :", cleaned[:120])
    print("VECTOR NNZ:", vec.nnz)
    print("PREDICTION:", prediction)
    print("-----------------")

    # ── Confidence ──────────────────────────────────────────────────────────
    if hasattr(model, "predict_proba"):
        proba      = model.predict_proba(vec)[0]
        confidence = int(round(max(proba) * 100))
    else:
        confidence = 85   # fallback if model has no probability output

    # ── NLP enrichment ──────────────────────────────────────────────────────
    keywords    = extract_keywords(text)
    sentiment   = analyze_sentiment(text)
    result      = "Real News" if prediction == 1 else "Fake News"
    explanation = build_explanation(text, prediction, confidence, keywords)

    # ── Save history ────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO history (user_id, text, result) VALUES (?, ?, ?)",
            (user_id, text, result)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "success":     True,
        "result":      result,
        "label":       int(prediction),
        "confidence":  confidence,
        "sentiment":   sentiment,
        "keywords":    keywords,
        "explanation": explanation
    })


# ------------------ HISTORY ------------------

@app.route("/history", methods=["GET"])
def get_history():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c    = conn.cursor()
    c.execute(
        "SELECT id, text, result, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {"id": r[0], "text": r[1], "result": r[2], "timestamp": r[3]}
        for r in rows
    ])


@app.route("/delete_history/<int:item_id>", methods=["DELETE"])
def delete_history(item_id):
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c    = conn.cursor()
    c.execute("DELETE FROM history WHERE id=? AND user_id=?", (item_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})


@app.route("/stats", methods=["GET"])
def stats():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (user_id,))
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND result='Real News'", (user_id,))
    real  = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND result='Fake News'", (user_id,))
    fake  = c.fetchone()[0]
    conn.close()
    return jsonify({"total": total, "real": real, "fake": fake})


# ------------------ CHANGE PASSWORD ------------------

@app.route("/change-password", methods=["POST"])
def change_password():
    data         = request.json
    username     = data.get("username")
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c    = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    if not user or not check_password_hash(user[1], old_password):
        conn.close()
        return jsonify({"success": False, "message": "Current password is incorrect"})
    c.execute("UPDATE users SET password=? WHERE username=?",
              (generate_password_hash(new_password), username))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ------------------ RUN ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)