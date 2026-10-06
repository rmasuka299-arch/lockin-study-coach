"""
LockIn: South African CAPS Study & Practice Coach (Grades 8–12)
Built with Streamlit & SQLite for offline, free local execution.
Full CAPS alignment:
- Senior Phase (Grades 8–9): Mathematics, Natural Sciences (NS), EMS, Social Sciences (SS), Technology, English, Life Orientation
- FET Phase (Grades 10–12): Mathematics, Mathematical Literacy, Physical Sciences, Life Sciences, Accounting, Business Studies, Economics, Geography, History, English, Life Orientation
- Instant reactive topic switching (zero lag)
- Illustrated SVG diagrams for every subject
- Persistent SQLite Daily Streak Counter & Diagnostic Dashboard
- 8 Aesthetic Themes & 3 Tone Modes (TikTok Slang, Casual Lekker, Formal Academic)
"""

import streamlit as st
import sqlite3
import random
import math
from datetime import datetime, date, timedelta
import pandas as pd
import json
import os
import secrets
import re
# Load AI-generated notes if the file exists
import streamlit as st
import json  # Added to allow python to parse your local files
from groq import Groq

# --- Groq client configuration setup ---


# 1. Load AI-generated notes if the file exists
try:
    with open("ai_notes.json", "r", encoding="utf-8") as f:
        AI_GENERATED_NOTES = json.load(f)
except Exception:
    AI_GENERATED_NOTES = {}

# 2. Load AI-generated questions if the file exists
try:
    with open("ai_questions.json", "r", encoding="utf-8") as f:
        AI_GENERATED_QUESTIONS = json.load(f)
except Exception:
    AI_GENERATED_QUESTIONS = {}

# 3. --- Groq client for AI Tutor Chat ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    groq_client = client
except Exception as e:
    st.error(f"Failed to boot Groq engine: {e}")
# 1. Initialize the Adaptive State Variables Safely
if "difficulty_level" not in st.session_state:
    st.session_state.difficulty_level = "Medium"  # Options: Easy, Medium, Hard
if "consecutive_correct" not in st.session_state:
    st.session_state.consecutive_correct = 0
# 4. Load AI formula sheets if the file exists
try:
    with open("ai_formula_sheets.json", "r", encoding="utf-8") as f:
        AI_FORMULA_SHEETS = json.load(f)
except Exception:
    AI_FORMULA_SHEETS = {}
def update_adaptive_difficulty(user_was_correct):
    """Dynamically adjusts the difficulty based on recent user performance."""
    if user_was_correct:
        st.session_state.consecutive_correct += 1
        
        # Level up rules
        if st.session_state.consecutive_correct >= 2:
            if st.session_state.difficulty_level == "Easy":
                st.session_state.difficulty_level = "Medium"
                st.session_state.consecutive_correct = 0  # Reset streak tracker
                st.toast("🔥 Level Up! Questions are getting trickier.")
            elif st.session_state.difficulty_level == "Medium":
                st.session_state.difficulty_level = "Hard"
                st.session_state.consecutive_correct = 0
                st.toast("⚡ Black Flash! You're entering the Hard tier.")
    else:
        # Reset the win streak instantly on a mistake
        st.session_state.consecutive_correct = 0
        
        # Level down rules to stabilize learning
        if st.session_state.difficulty_level == "Hard":
            st.session_state.difficulty_level = "Medium"
            st.toast("🛡️ Adjusting difficulty to help you rebuild your momentum.")
        elif st.session_state.difficulty_level == "Medium":
            st.session_state.difficulty_level = "Easy"
            st.toast("🔄 Stepping back to the basics. Let's master the foundation!")

# ---------------------------------------------------------
# 1. DATABASE & PERSISTENT STREAK SETUP (SQLite)
# ---------------------------------------------------------
DB_FILE = "lockin_study_coach.db"
class _NoOp:
    """A no-op context manager. Used to 'hide' tabs that aren't in the current section."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


# Section → tab mapping
TAB_CONFIG = {
       "📚 Study": ["notes", "flashcards", "formula", "diagram", "art"], 
    "🎯 Practice": ["practice", "boss", "paper", "panic"],
    "🤖 AI Help": ["chat", "essay"],
    "📊 Progress": ["dashboard", "mistakes", "planner", "readiness"],
    "ℹ️ Info": ["info"],
}

TAB_LABELS = {
    "practice": "📝 Practice Questions",
    "notes": "📖 Study Notes",
    "flashcards": "🃏 Flashcards Deck",
    "planner": "📅 Weekly Study Planner",
    "dashboard": "🏆 Badges & Analytics",
    "mistakes": "🩹 Mistake Journal",
    "chat": "💬 AI Tutor Chat",
    "essay": "📄 Essay Marker",
    "panic": "🚨 Panic Mode",
    "diagram": "🎨 Diagram Quiz",
    "art": "🎨 Math Art Studio",
    "boss": "⚔️ Boss Fight",
    "formula": "📐 Formula Sheets",
    "readiness": "📅 Exam Readiness",
    "paper": "📄 Full Mock Paper",
    "info": "ℹ️ CAPS Curriculum Guide",
}
# ============ HIDDEN MODE UNLOCK ============
SECRET_UNLOCK_CODE = "voestek"  # 👈 CHANGE TO YOUR SECRET WORD
SECRET_UNLOCK_CODE_2 = "zero"  # 👈 Change to whatever you want (Zero Mode)
def init_db():
    """Initialise SQLite tables with user_id migration."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # ---- USERS TABLE ----
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            grade INTEGER DEFAULT 8,
            gender TEXT DEFAULT '',
            preferred_tone TEXT DEFAULT 'casual',
            preferred_theme TEXT DEFAULT 'cyberpunk_neon',
            learning_style TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    # ---- ATTEMPTS TABLE ----
    c.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            grade INTEGER,
            subject TEXT,
            topic TEXT,
            subtopic TEXT,
            question TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            tone TEXT,
            timestamp TEXT
        )
    """)

    # Migration: add user_id column to old attempts table
    c.execute("PRAGMA table_info(attempts)")
    attempt_cols = [col[1] for col in c.fetchall()]
    if "user_id" not in attempt_cols:
        c.execute("ALTER TABLE attempts ADD COLUMN user_id INTEGER")

    # ---- STREAK_DATA TABLE (new schema: one row per user) ----
    c.execute("PRAGMA table_info(streak_data)")
    streak_cols = [col[1] for col in c.fetchall()]

    if "id" in streak_cols and "user_id" not in streak_cols:
        # OLD schema detected - migrate
        c.execute("SELECT current_streak, longest_streak, last_date FROM streak_data WHERE id = 1")
        old_streak = c.fetchone()
        c.execute("DROP TABLE streak_data")
        c.execute("""
            CREATE TABLE streak_data (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_date TEXT DEFAULT ''
            )
        """)
        # Reassign old streak to first user
        if old_streak:
            c.execute("SELECT id FROM users ORDER BY id LIMIT 1")
            row = c.fetchone()
            if row:
                c.execute("""
                    INSERT INTO streak_data (user_id, current_streak, longest_streak, last_date)
                    VALUES (?, ?, ?, ?)
                """, (row[0], old_streak[0], old_streak[1], old_streak[2]))
    else:
        # Fresh install OR already migrated
        c.execute("""
            CREATE TABLE IF NOT EXISTS streak_data (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_date TEXT DEFAULT ''
            )
        """)
        # Migration: add hints_used column to users
    c.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in c.fetchall()]
    if "hints_used" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN hints_used INTEGER DEFAULT 0")

    # ---- Assign orphan attempts to the first user (Axel) ----
    c.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = c.fetchone()
    if row:
        first_uid = row[0]
        c.execute("UPDATE attempts SET user_id = ? WHERE user_id IS NULL", (first_uid,))
        # Ensure streak row exists
        c.execute("SELECT COUNT(*) FROM streak_data WHERE user_id = ?", (first_uid,))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO streak_data (user_id) VALUES (?)", (first_uid,))

    conn.commit()
    conn.close()
import hashlib
def get_hints_used(user_id):
    """How many hints this user has used (each costs 5 XP)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COALESCE(hints_used, 0) FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def record_hint_used(user_id):
    """Increment the hint counter for this user."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET hints_used = COALESCE(hints_used, 0) + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def hash_password(password, salt=None):
    """Hash a password with a random salt (PBKDF2 - industry standard)."""
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password, stored_hash):
    """Check if a password matches a stored hash."""
    try:
        salt, _ = stored_hash.split('$')
        return hash_password(password, salt) == stored_hash
    except Exception:
        return False


def create_user(username, password, display_name, grade, gender, preferred_tone, preferred_theme, learning_style):
    """Insert a new user + initialize their streak row."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, display_name, grade, gender,
                             preferred_tone, preferred_theme, learning_style, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username.lower().strip(),
            hash_password(password),
            display_name.strip(),
            grade,
            gender,
            preferred_tone,
            preferred_theme,
            learning_style,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        new_uid = c.lastrowid
        # Give them a fresh streak row
        c.execute("INSERT INTO streak_data (user_id, current_streak, longest_streak, last_date) VALUES (?, 0, 0, '')", (new_uid,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    """Return user dict if login is valid, else None."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, password_hash, display_name, grade, gender,
               preferred_tone, preferred_theme, learning_style
        FROM users WHERE username = ?
    """, (username.lower().strip(),))
    row = c.fetchone()
    conn.close()

    if row and verify_password(password, row[1]):
        return {
            "id": row[0],
            "username": username,
            "display_name": row[2],
            "grade": row[3],
            "gender": row[4],
            "preferred_tone": row[5],
            "preferred_theme": row[6],
            "learning_style": row[7],
        }
    return None
def create_session(user_id):
    """Generate a session token and save it. Returns the token."""
    token = secrets.token_urlsafe(32)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Self-healing: ensure table exists every time
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT
        )
    """)
    c.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
              (token, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return token


def get_user_by_session(token):
    """Look up a user from a session token. Returns user dict or None."""
    if not token:
        return None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT
        )
    """)
    c.execute("""
        SELECT u.id, u.username, u.display_name, u.grade, u.gender,
               u.preferred_tone, u.preferred_theme, u.learning_style
        FROM users u
        JOIN sessions s ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "grade": row[3],
            "gender": row[4],
            "preferred_tone": row[5],
            "preferred_theme": row[6],
            "learning_style": row[7],
        }
    return None


def delete_session(token):
    """Remove a session token (called on logout)."""
    if not token:
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_user_count():
    """How many users are signed up (nice for stats)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    n = c.fetchone()[0]
    conn.close()
    return n
def get_streak_info(user_id):
    """Retrieve current daily streak data for a specific user."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT current_streak, longest_streak, last_date FROM streak_data WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return 0, 0, ""
    return row[0], row[1], row[2]
# ... right after your database get_streak_info(user_id) function ...

# 👇 PASTE THE DYNAMIC FUNCTION LOGIC RIGHT HERE:
def update_adaptive_difficulty(user_was_correct):
    """Dynamically adjusts the difficulty based on recent user performance."""
    if user_was_correct:
        st.session_state.consecutive_correct += 1
        if st.session_state.consecutive_correct >= 2:
            if st.session_state.difficulty_level == "Easy":
                st.session_state.difficulty_level = "Medium"
                st.session_state.consecutive_correct = 0
                st.toast("🔥 Level Up! Questions are getting trickier.")
            elif st.session_state.difficulty_level == "Medium":
                st.session_state.difficulty_level = "Hard"
                st.session_state.consecutive_correct = 0
                st.toast("⚡ Black Flash! You're entering the Hard tier.")
    else:
        st.session_state.consecutive_correct = 0
        if st.session_state.difficulty_level == "Hard":
            st.session_state.difficulty_level = "Medium"
            st.toast("🛡️ Adjusting difficulty to help you rebuild momentum.")
        elif st.session_state.difficulty_level == "Medium":
            st.session_state.difficulty_level = "Easy"
            st.toast("🔄 Stepping back to master the foundation!")

def record_practice_attempt(user_id, grade, subject, topic, subtopic, question, user_ans, correct_ans, is_correct, tone):
    """Save user attempt and update that user's daily streak."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = date.today().isoformat()

    c.execute("""
        INSERT INTO attempts (user_id, grade, subject, topic, subtopic, question, user_answer, correct_answer, is_correct, tone, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, grade, subject, topic, subtopic, question, str(user_ans), str(correct_ans), 1 if is_correct else 0, tone, now_str))

    # Get this user's streak
    c.execute("SELECT current_streak, longest_streak, last_date FROM streak_data WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row is None:
        # First time - create row
        curr, longest, last_d = 0, 0, ""
        c.execute("INSERT INTO streak_data (user_id, current_streak, longest_streak, last_date) VALUES (?, 0, 0, '')", (user_id,))
    else:
        curr, longest, last_d = row

    if last_d != today_str:
        if last_d:
            last_dt = datetime.strptime(last_d, "%Y-%m-%d").date()
            yesterday = date.today() - timedelta(days=1)
            if last_dt == yesterday:
                curr += 1
            else:
                curr = 1
        else:
            curr = 1

        if curr > longest:
            longest = curr
        c.execute("UPDATE streak_data SET current_streak = ?, longest_streak = ?, last_date = ? WHERE user_id = ?",
                  (curr, longest, today_str, user_id))

    conn.commit()
    conn.close()
def get_attempts_df(user_id=None):
    """Fetch stored practice records (optionally filtered by user)."""
    conn = sqlite3.connect(DB_FILE)
    try:
        if user_id is not None:
            df = pd.read_sql_query("SELECT * FROM attempts WHERE user_id = ?", conn, params=(user_id,))
        else:
            df = pd.read_sql_query("SELECT * FROM attempts", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df
def reset_all_data(user_id):
    """Reset this user's progress only."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
    c.execute("UPDATE streak_data SET current_streak = 0, longest_streak = 0, last_date = '' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
# ---------------------------------------------------------
# 1B. ACHIEVEMENT BADGES & FLASHCARDS DATA BANK
# ---------------------------------------------------------
BADGES_CONFIG = [
    {"id": "first_lockin", "name": "First LockIn", "icon": "🎯", "desc": "Complete your very first practice question", "target": 1, "type": "total"},
    {"id": "streak_3", "name": "Heating Up", "icon": "🔥", "desc": "Maintain an active 3-day study streak", "target": 3, "type": "streak"},
    {"id": "streak_7", "name": "Consistency King", "icon": "⚡", "desc": "Reach a 7-day study streak", "target": 7, "type": "streak"},
    {"id": "dedicated_25", "name": "Dedicated Learner", "icon": "📚", "desc": "Solve 25 practice questions", "target": 25, "type": "total"},
    {"id": "century_club", "name": "Century Club", "icon": "💯", "desc": "Solve 100 questions across any subjects", "target": 100, "type": "total"},
    {"id": "maths_whiz", "name": "Maths Whiz", "icon": "📐", "desc": "Get 10 Mathematics questions correct", "target": 10, "type": "subject_math"},
    {"id": "science_pioneer", "name": "Science Pioneer", "icon": "🔬", "desc": "Get 10 Science questions correct", "target": 10, "type": "subject_sci"},
    {"id": "wordsmith", "name": "Wordsmith", "icon": "✍️", "desc": "Get 10 English questions correct", "target": 10, "type": "subject_eng"},
    {"id": "level_7_exam", "name": "Matric Level 7", "icon": "🏆", "desc": "Score 80%+ in a Timed CAPS Exam", "target": 1, "type": "exam_level7"},
]

def compute_badges(df, curr_streak, has_level_7=False):
    """Evaluate student badges based on attempts history and streaks."""
    total_solved = len(df)
    math_correct = len(df[(df["subject"].str.lower().str.contains("math", na=False)) & (df["is_correct"] == 1)]) if not df.empty else 0
    sci_correct = len(df[(df["subject"].str.lower().str.contains("science", na=False)) & (df["is_correct"] == 1)]) if not df.empty else 0
    eng_correct = len(df[(df["subject"].str.lower().str.contains("english", na=False)) & (df["is_correct"] == 1)]) if not df.empty else 0

    results = []
    for b in BADGES_CONFIG:
        progress = 0
        if b["type"] == "total":
            progress = total_solved
        elif b["type"] == "streak":
            progress = curr_streak
        elif b["type"] == "subject_math":
            progress = math_correct
        elif b["type"] == "subject_sci":
            progress = sci_correct
        elif b["type"] == "subject_eng":
            progress = eng_correct
        elif b["type"] == "exam_level7":
            progress = 1 if has_level_7 else 0

        unlocked = progress >= b["target"]
        results.append({
            "id": b["id"],
            "name": b["name"],
            "icon": b["icon"],
            "desc": b["desc"],
            "target": b["target"],
            "progress": min(progress, b["target"]),
            "unlocked": unlocked
        })
    return results

CAPS_FLASHCARDS = {
    "mathematics": [
        {"front": "Theorem of Pythagoras", "back": "In any right-angled triangle: c² = a² + b² (hypotenuse² = sum of squares of other two sides)."},
        {"front": "Quadratic Formula", "back": "For ax² + bx + c = 0: x = (-b ± √(b² - 4ac)) / 2a. The discriminant Δ = b² - 4ac determines the nature of roots."},
        {"front": "Gradient Formula (Analytical Geometry)", "back": "Slope of line joining (x₁, y₁) and (x₂, y₂): m = (y₂ - y₁) / (x₂ - x₁)."},
        {"front": "Trigonometric Identity", "back": "For any angle θ: sin²θ + cos²θ = 1, and tanθ = sinθ / cosθ."},
        {"front": "Derivative from First Principles", "back": "Gradient of tangent to f(x): f'(x) = lim(h→0) [f(x+h) - f(x)] / h."}
    ],
    "natural_sciences": [
        {"front": "Photosynthesis Word Equation", "back": "Carbon Dioxide + Water + Sunlight → Glucose + Oxygen. Balanced: 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂."},
        {"front": "Ohm's Law", "back": "The potential difference across a conductor is directly proportional to the current (at constant temperature). Formula: V = I × R."},
        {"front": "Digestive Enzymes", "back": "Amylase: starches → maltose (mouth/pancreas). Pepsin: proteins → peptides (stomach, pH 2). Lipase: lipids → glycerol + fatty acids."}
    ],
    "physical_sciences": [
        {"front": "Newton's First Law", "back": "An object continues in its state of rest or uniform velocity unless acted upon by a net external force."},
        {"front": "Newton's Second Law", "back": "Net force equals mass times acceleration: F_net = m × a."},
        {"front": "Work-Energy Theorem", "back": "Net work done on an object equals the change in kinetic energy: W_net = ΔE_k = ½mv_f² - ½mv_i²."},
        {"front": "Doppler Effect (Sound)", "back": "Apparent frequency change when source and listener have relative velocity: f_L = [(v ± v_L) / (v ∓ v_s)] × f_s."}
    ],
    "life_sciences": [
        {"front": "DNA vs RNA Structure", "back": "DNA: double-stranded, deoxyribose sugar, thymine (A-T, C-G). RNA: single-stranded, ribose sugar, uracil (A-U, C-G)."},
        {"front": "Stages of Mitosis", "back": "1. Prophase (chromatin condenses). 2. Metaphase (chromosomes align at equator). 3. Anaphase (sister chromatids separate). 4. Telophase (nuclear envelopes reform)."},
        {"front": "Law of Segregation (Mendel)", "back": "Each organism has two alleles for each gene. These separate during gamete formation, so each gamete carries only one allele."}
    ],
    "ems": [
        {"front": "The Fundamental Accounting Equation", "back": "Assets = Owner's Equity + Liabilities. Written: A = O + L."},
        {"front": "Cash Receipts Journal (CRJ)", "back": "A subsidiary book used to record all incoming money (cash and direct bank deposits) received by the business."},
        {"front": "Economic Law of Demand", "back": "As the price of a good increases, the quantity demanded decreases (ceteris paribus)."}
    ]
}

CAPS_STUDY_NOTES = {
    "mathematics": {
        "subject_name": "Mathematics",
        "curriculum_overview": "CAPS Mathematics focuses on algebra, functions, geometry, trigonometry, and calculus across Grades 8\u201312.",
        "chapters": [
            {
                "title": "Algebraic Equations & Factorisation",
                "grades": [
                    8,
                    9,
                    10,
                    11,
                    12
                ],
                "summary": "Factorisation is the foundation of algebra. Core techniques include common factors, difference of two squares, trinomials, grouping in pairs, and the quadratic formula.",
                "definitions": [
                    [
                        "Trinomial",
                        "An algebraic expression consisting of three terms, typically in the form ax\u00b2 + bx + c."
                    ],
                    [
                        "Discriminant (\u0394)",
                        "\u0394 = b\u00b2 - 4ac. Determines the nature of roots: real, equal, non-real, or rational."
                    ]
                ],
                "formulas": [
                    [
                        "Quadratic Formula",
                        "x = (-b \u00b1 \u221a(b\u00b2 - 4ac)) / (2a)",
                        "Used when trinomial cannot be easily factorised"
                    ],
                    [
                        "Difference of Squares",
                        "a\u00b2 - b\u00b2 = (a - b)(a + b)",
                        "Terms must be perfect squares separated by a minus"
                    ]
                ],
                "worked_example": {
                    "problem": "Solve for x: 2x\u00b2 - 5x - 3 = 0",
                    "steps": [
                        "1. Identify coefficients: a = 2, b = -5, c = -3",
                        "2. Factorise the quadratic: (2x + 1)(x - 3) = 0",
                        "3. Set each factor equal to zero: 2x + 1 = 0 or x - 3 = 0",
                        "4. Solve for x: x = -1/2 or x = 3"
                    ],
                    "answer": "x = -1/2 or x = 3"
                },
                "pitfalls": [
                    "Dividing by a variable: Never divide both sides by x as you eliminate the x = 0 root.",
                    "Sign errors when applying the quadratic formula: -(-b) becomes positive."
                ],
                "tips": [
                    "Always look for a common factor FIRST before attempting trinomial factorisation.",
                    "Check your roots by substituting back into the original equation."
                ]
            },
            {
                "title": "Euclidean Geometry & Circle Theorems",
                "grades": [
                    8,
                    9,
                    10,
                    11,
                    12
                ],
                "summary": "Deals with properties of triangles, parallel lines, quadrilaterals, and circle geometry theorems.",
                "definitions": [
                    [
                        "Subtended Angle",
                        "An angle created by two line segments extending from the ends of an arc or chord."
                    ],
                    [
                        "Cyclic Quadrilateral",
                        "A four-sided polygon whose four vertices all lie on the circumference of a circle."
                    ]
                ],
                "formulas": [
                    [
                        "Angle at Centre",
                        "Angle at centre = 2 \u00d7 Angle at circumference",
                        "Reason: (\u2220 at centre = 2 \u00d7 \u2220 at circumf)"
                    ],
                    [
                        "Opposite Angles of Cyclic Quad",
                        "\u2220A + \u2220C = 180\u00b0",
                        "Reason: (opp \u2220s of cyclic quad supp)"
                    ]
                ],
                "worked_example": {
                    "problem": "In circle with centre O, arc AB subtends 80\u00b0 at O. Calculate the angle subtended by AB at point C on the circumference.",
                    "steps": [
                        "1. Identify theorem: Angle at centre = 2 \u00d7 angle at circumference.",
                        "2. Set up equation: \u2220AOB = 2 \u00d7 \u2220ACB",
                        "3. Substitute: 80\u00b0 = 2 \u00d7 \u2220ACB => \u2220ACB = 80\u00b0 / 2 = 40\u00b0",
                        "4. Provide CAPS mandatory geometric reason."
                    ],
                    "answer": "\u2220ACB = 40\u00b0 (\u2220 at centre = 2 \u00d7 \u2220 at circumf)"
                },
                "pitfalls": [
                    "Omitting CAPS geometric reasons loses 50% of available marks in Geometry.",
                    "Assuming a line is a diameter or tangent without given proof."
                ],
                "tips": [
                    "Highlight given radii as they form isosceles triangles (radii are equal).",
                    "Remember the tan-chord theorem whenever a tangent touches a triangle in a circle."
                ]
            }
        ]
    },
    "natural_sciences": {
        "subject_name": "Natural Sciences",
        "curriculum_overview": "Covers Life and Living, Matter and Materials, Energy and Change, and Planet Earth and Beyond for Grades 8 & 9.",
        "chapters": [
            {
                "title": "Human Digestive System & Nutrition",
                "grades": [
                    8,
                    9
                ],
                "summary": "Covers the mechanical and chemical breakdown of food into nutrients that can be absorbed into the bloodstream.",
                "definitions": [
                    [
                        "Peristalsis",
                        "Rhythmic wave-like muscular contractions of the alimentary canal that move food bolus downward."
                    ],
                    [
                        "Enzyme",
                        "A biological protein catalyst that accelerates metabolic reactions without being consumed."
                    ]
                ],
                "formulas": [
                    [
                        "Respiration Word Equation",
                        "Glucose + Oxygen -> Carbon Dioxide + Water + ATP Energy",
                        "Occurs in the mitochondria of all cells"
                    ]
                ],
                "worked_example": {
                    "problem": "Explain the role of hydrochloric acid (HCl) in the human stomach.",
                    "steps": [
                        "1. Lowers the pH of gastric juice to 1.5 - 2.0 (highly acidic).",
                        "2. Provides the optimal acidic environment for pepsin enzyme activation.",
                        "3. Kills harmful bacteria and pathogens ingested with food."
                    ],
                    "answer": "Kills pathogens and activates pepsinogen into active pepsin enzyme."
                },
                "pitfalls": [
                    "Confusing ingestion (taking in food) with absorption (nutrients entering the bloodstream).",
                    "Forgetting that bile is produced in the liver and stored in the gall bladder."
                ],
                "tips": [
                    "Remember the 4 stages: Ingestion -> Digestion -> Absorption -> Egestion.",
                    "Know where each enzyme acts: Amylase in mouth, Pepsin in stomach, Lipase in small intestine."
                ]
            },
            {
                "title": "Electric Circuits, Current & Resistance",
                "grades": [
                    8,
                    9
                ],
                "summary": "Study of electric current (I), potential difference (V), and resistance (R) in series and parallel circuits.",
                "definitions": [
                    [
                        "Current (I)",
                        "The rate of flow of electric charge per second, measured in Amperes (A)."
                    ],
                    [
                        "Potential Difference (V)",
                        "The work done per unit electric charge as it passes between two points, measured in Volts (V)."
                    ]
                ],
                "formulas": [
                    [
                        "Ohm's Law",
                        "V = I \u00d7 R",
                        "V in Volts, I in Amps, R in Ohms"
                    ],
                    [
                        "Series Resistance",
                        "R_total = R1 + R2 + ...",
                        "Total resistance increases as more resistors are added"
                    ]
                ],
                "worked_example": {
                    "problem": "A 12V battery is connected to a 4\u03a9 resistor. Calculate the current flowing through the circuit.",
                    "steps": [
                        "1. Write the formula: V = I \u00d7 R",
                        "2. Rearrange for current: I = V / R",
                        "3. Substitute values: I = 12 / 4 = 3 A"
                    ],
                    "answer": "Current I = 3 A"
                },
                "pitfalls": [
                    "Connecting an ammeter in parallel (it has near-zero resistance and causes a short circuit).",
                    "Forgetting that parallel branches divide current while voltage remains the same across each branch."
                ],
                "tips": [
                    "Ammeters are always wired in SERIES; voltmeters are always wired in PARALLEL.",
                    "Adding more resistors in parallel DECREASES total resistance and increases overall current."
                ]
            }
        ]
    },
    "ems": {
        "subject_name": "Economic & Management Sciences",
        "curriculum_overview": "Integrates financial literacy (accounting journals & equations) and the economy (markets, entrepreneurship) for Grades 8 & 9.",
        "chapters": [
            {
                "title": "The Accounting Equation & Double-Entry Principle",
                "grades": [
                    8,
                    9
                ],
                "summary": "Every financial transaction has a dual effect on Assets (A), Owner's Equity (OE), and Liabilities (L).",
                "definitions": [
                    [
                        "Asset",
                        "A resource owned by a business that has future economic value (e.g., Equipment, Bank, Trading Stock)."
                    ],
                    [
                        "Liability",
                        "Debts or financial obligations owed by the business to external third parties (e.g., Bank Loan, Creditors)."
                    ]
                ],
                "formulas": [
                    [
                        "The Accounting Equation",
                        "Assets = Owner's Equity + Liabilities (A = OE + L)",
                        "Fundamental equation must always balance"
                    ]
                ],
                "worked_example": {
                    "problem": "Owner deposits R50,000 cash into the business bank account as initial capital contribution. Analyze the effect on A = OE + L.",
                    "steps": [
                        "1. Source document: Bank deposit slip / electronic receipt.",
                        "2. Account Debited: Bank (Asset increases by +R50,000).",
                        "3. Account Credited: Capital (Owner's Equity increases by +R50,000).",
                        "4. Effect on equation: A (+50,000) = OE (+50,000) + L (0)."
                    ],
                    "answer": "Assets (+50,000) = Owner's Equity (+50,000) + Liabilities (0)"
                },
                "pitfalls": [
                    "Confusing expenses with liabilities. An expense reduces OE, whereas a liability is money owed to outsiders.",
                    "Treating drawings as an asset instead of a reduction in Owner's Equity."
                ],
                "tips": [
                    "Remember DEAD CLIC: Debit Expenses, Assets, Drawings; Credit Liabilities, Income, Capital.",
                    "Double check that the equation (A = OE + L) balances after every single transaction."
                ]
            }
        ]
    },
    "social_sciences": {
        "subject_name": "Social Sciences",
        "curriculum_overview": "Combines Geography (mapwork, climate, settlements) and History (colonialism, mineral revolution, struggle) for Grades 8 & 9.",
        "chapters": [
            {
                "title": "Topographical Mapwork & Contour Lines",
                "grades": [
                    8,
                    9
                ],
                "summary": "Reading 1:50 000 topographic maps, calculating distance, contour intervals, and identifying landforms.",
                "definitions": [
                    [
                        "Contour Line",
                        "A line drawn on a map joining all points that have the exact same elevation above sea level."
                    ],
                    [
                        "Contour Interval",
                        "The vertical height difference between two adjacent contour lines (standard 20m on 1:50 000 SA maps)."
                    ]
                ],
                "formulas": [
                    [
                        "Map Distance Conversion",
                        "Real Distance (km) = Map Distance (cm) \u00d7 0.5 km",
                        "On a 1:50 000 scale map, 1cm represents 500m (0.5km)"
                    ]
                ],
                "worked_example": {
                    "problem": "Two trig beacons are 6.4 cm apart on a 1:50 000 topographic map. Calculate real-world ground distance in kilometres.",
                    "steps": [
                        "1. Note the scale: 1 cm on map = 50,000 cm on ground = 500 m = 0.5 km.",
                        "2. Multiply: Real Distance = 6.4 cm \u00d7 0.5 km/cm = 3.2 km."
                    ],
                    "answer": "3.2 km"
                },
                "pitfalls": [
                    "Measuring straight-line distance instead of following road or river curves when asked for route distance.",
                    "Confusing steep slopes (close contour lines) with gentle slopes (widely spaced contours)."
                ],
                "tips": [
                    "Contour lines pointing in a V-shape pointing upstream indicate a river valley.",
                    "Always double check whether the question asks for metres or kilometres."
                ]
            }
        ]
    },
    "technology": {
        "subject_name": "Technology",
        "curriculum_overview": "Explores the design process, structures, mechanical systems (levers, gears, hydraulics), and electrical circuits for Grades 8 & 9.",
        "chapters": [
            {
                "title": "Mechanical Systems: Levers & Mechanical Advantage",
                "grades": [
                    8,
                    9
                ],
                "summary": "Covers First, Second, and Third Class levers, fulcrum placement, effort, and load mechanical advantage.",
                "definitions": [
                    [
                        "Mechanical Advantage (MA)",
                        "The factor by which a mechanism multiplies the input effort force: MA = Load / Effort."
                    ],
                    [
                        "Fulcrum",
                        "The pivot point around which a lever moves."
                    ]
                ],
                "formulas": [
                    [
                        "Mechanical Advantage",
                        "MA = Load / Effort = Distance of Effort / Distance of Load",
                        "MA > 1 means force multiplication"
                    ]
                ],
                "worked_example": {
                    "problem": "A crowbar lifts a 600N boulder using an effort force of 150N. Calculate the mechanical advantage.",
                    "steps": [
                        "1. Write formula: MA = Load / Effort",
                        "2. Substitute values: MA = 600 N / 150 N = 4"
                    ],
                    "answer": "MA = 4 (no units for mechanical advantage)"
                },
                "pitfalls": [
                    "Assigning units to MA. Mechanical advantage is a pure ratio and has no units.",
                    "Confusing Class 2 levers (Load in middle, e.g. wheelbarrow) with Class 3 levers (Effort in middle, e.g. tweezers)."
                ],
                "tips": [
                    "Remember FLE 1-2-3: Class 1 has Fulcrum in middle, Class 2 has Load in middle, Class 3 has Effort in middle."
                ]
            }
        ]
    },
    "physical_sciences": {
        "subject_name": "Physical Sciences",
        "curriculum_overview": "Physics (Mechanics, Waves, Electricity & Magnetism) and Chemistry (Matter, Chemical Change, Organic Chemistry) for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Newton's Laws of Motion & Momentum",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Mechanics foundations: Newton's 1st, 2nd, and 3rd laws, free-body diagrams, friction, and conservation of linear momentum.",
                "definitions": [
                    [
                        "Newton's First Law",
                        "An object continues in its state of rest or uniform velocity in a straight line unless acted upon by a non-zero net external force."
                    ],
                    [
                        "Newton's Second Law",
                        "When a net force acts on an object of mass m, the object accelerates in the direction of the force with an acceleration directly proportional to the force and inversely proportional to mass: F_net = m\u00b7a."
                    ],
                    [
                        "Principle of Conservation of Momentum",
                        "The total linear momentum of an isolated system remains constant in both magnitude and direction."
                    ]
                ],
                "formulas": [
                    [
                        "Newton's Second Law",
                        "F_net = m \u00d7 a",
                        "Force in N, mass in kg, acceleration in m\u00b7s\u207b\u00b2"
                    ],
                    [
                        "Kinetic Friction",
                        "f_k = \u03bc_k \u00d7 N",
                        "N is normal force in N"
                    ],
                    [
                        "Linear Momentum",
                        "p = m \u00d7 v",
                        "Momentum in kg\u00b7m\u00b7s\u207b\u00b9"
                    ]
                ],
                "worked_example": {
                    "problem": "A 5 kg crate on a horizontal rough floor is pulled by a 30 N force to the right. The frictional force is 10 N. Calculate the acceleration of the crate.",
                    "steps": [
                        "1. Calculate net horizontal force: F_net = F_applied - f_k = 30 - 10 = 20 N right.",
                        "2. Apply Newton's 2nd Law: F_net = m \u00d7 a",
                        "3. Substitute: 20 = 5 \u00d7 a => a = 20 / 5 = 4 m\u00b7s\u207b\u00b2 to the right."
                    ],
                    "answer": "a = 4 m\u00b7s\u207b\u00b2 to the right"
                },
                "pitfalls": [
                    "Omitting direction in vector answers (velocity, acceleration, force, momentum all require direction).",
                    "Drawing forces touching the wrong body in free-body diagrams."
                ],
                "tips": [
                    "Always draw a labelled free-body diagram before writing any equation of motion.",
                    "Take a chosen direction as positive (e.g. right = +) and stick with it consistently."
                ]
            },
            {
                "title": "Organic Chemistry: Functional Groups & IUPAC Naming",
                "grades": [
                    11,
                    12
                ],
                "summary": "Hydrocarbons, homologous series, functional groups, structural isomerism, and intermolecular forces determining physical properties.",
                "definitions": [
                    [
                        "Homologous Series",
                        "A series of organic compounds that can be described by the same general formula and where each member differs from the next by a -CH\u2082- group."
                    ],
                    [
                        "Functional Group",
                        "An atom or group of atoms that forms the center of chemical activity in the molecule."
                    ],
                    [
                        "Structural Isomer",
                        "Organic molecules having the same molecular formula, but different structural formulae."
                    ]
                ],
                "formulas": [
                    [
                        "Alkanes General Formula",
                        "C_n H_(2n+2)",
                        "Saturated hydrocarbons (single bonds only)"
                    ],
                    [
                        "Alkenes General Formula",
                        "C_n H_(2n)",
                        "Unsaturated hydrocarbons with one double bond C=C"
                    ],
                    [
                        "Alcohols Functional Group",
                        "-OH (Hydroxyl group)",
                        "Suffix -ol"
                    ]
                ],
                "worked_example": {
                    "problem": "Give the IUPAC name for CH3-CH(CH3)-CH2-CH2-OH.",
                    "steps": [
                        "1. Identify the principal functional group: -OH group (alcohol suffix -ol).",
                        "2. Find the longest carbon chain containing the -OH group: 4 carbons (butan-).",
                        "3. Number chain from end closest to -OH: Carbon 1 has -OH, Carbon 3 has a methyl substituent (-CH3).",
                        "4. Combine components: 3-methylbutan-1-ol."
                    ],
                    "answer": "3-methylbutan-1-ol"
                },
                "pitfalls": [
                    "Forgetting commas between numbers (e.g. 2,2-dimethyl) and hyphens between numbers and letters (e.g. 2-methyl).",
                    "Confusing intermolecular forces (hydrogen bonding) with intramolecular bonds (covalent bonds)."
                ],
                "tips": [
                    "Carboxylic acids and alcohols form hydrogen bonds, resulting in significantly higher boiling points than alkanes or esters.",
                    "When explaining boiling points, follow the 3-step CAPS marking criteria: Type of intermolecular force, strength comparison, energy required to overcome."
                ]
            }
        ]
    },
    "life_sciences": {
        "subject_name": "Life Sciences",
        "curriculum_overview": "Genetics & Inheritance, Evolution, Human Reproduction, Endocrine System, Homeostasis, and Plant Responses for Grades 10\u201312.",
        "chapters": [
            {
                "title": "DNA: The Code of Life & Protein Synthesis",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Structure of nucleic acids (DNA and RNA), semi-conservative DNA replication, transcription in the nucleus, and translation at ribosomes.",
                "definitions": [
                    [
                        "Gene",
                        "A segment of DNA on a chromosome that codes for a specific functional protein or characteristic."
                    ],
                    [
                        "Transcription",
                        "The process where the genetic code of DNA is copied onto a complementary messenger RNA (mRNA) molecule in the nucleus."
                    ],
                    [
                        "Translation",
                        "The process in which the mRNA sequence is decoded at the ribosome into a specific sequence of amino acids to form a polypeptide chain."
                    ]
                ],
                "formulas": [
                    [
                        "Complementary Base Pairing in DNA",
                        "Adenine (A) pairs with Thymine (T) [2 H-bonds]; Cytosine (C) pairs with Guanine (G) [3 H-bonds]",
                        "In RNA, Uracil (U) replaces Thymine"
                    ]
                ],
                "worked_example": {
                    "problem": "A template strand of DNA has the base sequence: 3'-TAC GGC TTA-5'. State the complementary mRNA sequence and tRNA anticodons.",
                    "steps": [
                        "1. Transcribe DNA to mRNA (A pairs with U, T with A, C with G, G with C):",
                        "   DNA:  T - A - C   G - G - C   T - T - A",
                        "   mRNA: A - U - G   C - C - G   A - A - U",
                        "2. Determine tRNA anticodons complementary to mRNA codons:",
                        "   tRNA: U - A - C   G - G - C   U - U - A"
                    ],
                    "answer": "mRNA: 5'-AUG CCG AAU-3' | tRNA anticodons: UAC, GGC, UUA"
                },
                "pitfalls": [
                    "Writing Thymine (T) in an RNA sequence. RNA NEVER contains Thymine; it contains Uracil (U).",
                    "Confusing codon (on mRNA) with anticodon (on tRNA)."
                ],
                "tips": [
                    "Always mention where each process happens: Transcription in the NUCLEUS, Translation at the RIBOSOME.",
                    "In protein synthesis questions, peptide bonds join amino acids together."
                ]
            },
            {
                "title": "Genetics & Monohybrid Inheritance",
                "grades": [
                    11,
                    12
                ],
                "summary": "Mendel's laws, monohybrid crosses, sex-linked conditions (haemophilia, red-green colour blindness), and pedigree diagrams.",
                "definitions": [
                    [
                        "Allele",
                        "Alternative forms of a gene located at the same locus on homologous chromosomes."
                    ],
                    [
                        "Homozygous",
                        "An organism carrying two identical alleles for a specific gene (e.g. BB or bb)."
                    ],
                    [
                        "Heterozygous",
                        "An organism carrying two different alleles for a specific gene (e.g. Bb)."
                    ]
                ],
                "formulas": [
                    [
                        "Standard Monohybrid Phenotypic Ratio",
                        "3 dominant : 1 recessive (when crossing two heterozygous parents Bb \u00d7 Bb)",
                        "Genotypic ratio: 1 BB : 2 Bb : 1 bb"
                    ]
                ],
                "worked_example": {
                    "problem": "In pea plants, tall (T) is dominant over short (t). Cross a heterozygous tall plant (Tt) with a short plant (tt). Show the genetic cross.",
                    "steps": [
                        "1. State P1 Phenotype: Tall \u00d7 Short",
                        "2. State P1 Genotype: Tt \u00d7 tt",
                        "3. Meiosis / Gametes: T, t  \u00d7  t, t",
                        "4. Punnett Square fertilisation: Tt, Tt, tt, tt",
                        "5. F1 Genotypes: 50% Tt, 50% tt",
                        "6. F1 Phenotypes: 50% Tall, 50% Short (1 : 1 ratio)"
                    ],
                    "answer": "50% Tall, 50% Short (Ratio 1:1)"
                },
                "pitfalls": [
                    "Forgetting the compulsory genetic cross template in DBE exams (loses up to 3 format marks).",
                    "Placing alleles on the Y chromosome for sex-linked disorders. Haemophilia alleles are carried ONLY on the X chromosome."
                ],
                "tips": [
                    "Always write P1, Meiosis, Gametes, Fertilisation, F1 Genotypes, and F1 Phenotypes explicitly."
                ]
            }
        ]
    },
    "accounting": {
        "subject_name": "Accounting",
        "curriculum_overview": "Financial Accounting, Managerial Accounting, Internal Control, Ethics, and Auditing for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Bank Reconciliation & Internal Control",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Reconciling the business Bank Account balance in the General Ledger with the Bank Statement received from the financial institution.",
                "definitions": [
                    [
                        "Outstanding Deposit",
                        "Money received and recorded in the CRJ, but not yet reflected on the bank statement by the closing date."
                    ],
                    [
                        "Uncredited Cheque / EFT",
                        "A payment recorded in the CPJ, but not yet cleared or processed by the payee's bank."
                    ]
                ],
                "formulas": [
                    [
                        "Reconciliation Balancing Check",
                        "Bank Account Balance in Ledger = Bank Statement Balance (adjusted for timing differences)",
                        "Must equal zero net discrepancy"
                    ]
                ],
                "worked_example": {
                    "problem": "Bank account shows R15,400 debit balance. Bank statement shows bank charges R350 and interest received R120 not yet recorded in business journals. Update the bank balance.",
                    "steps": [
                        "1. Interest received (R120) is recorded in CRJ: increases bank balance (+R120).",
                        "2. Bank charges (R350) are recorded in CPJ: decreases bank balance (-R350).",
                        "3. Adjusted Bank Balance = R15,400 + R120 - R350 = R15,170."
                    ],
                    "answer": "Adjusted Bank Balance = R15,170 Debit"
                },
                "pitfalls": [
                    "In business books, Bank with a Debit balance is an Asset; in Bank records, your deposit is a Credit balance (liability to the bank).",
                    "Forgetting to cancel stale cheques (cheques older than 6 months)."
                ],
                "tips": [
                    "Update subsidiary journals (CRJ & CPJ) FIRST before drafting the Bank Reconciliation Statement.",
                    "Only items on the bank statement missing from journals go to journals; items in journals missing from statement go to the Bank Reconciliation Statement."
                ]
            }
        ]
    },
    "business_studies": {
        "subject_name": "Business Studies",
        "curriculum_overview": "Business Environments, Business Ventures, Business Roles, and Business Operations for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Business Environments: Micro, Market & Macro",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Analyzing the 3 business environments, extent of management control, and strategic management tools (SWOT, Porter's Five Forces, PESTLE).",
                "definitions": [
                    [
                        "Micro Environment",
                        "Internal business factors completely within management's direct control (Mission, Vision, 8 Business Functions)."
                    ],
                    [
                        "Market Environment",
                        "Industry factors immediately outside the business where management can only exert influence (Customers, Competitors, Suppliers)."
                    ],
                    [
                        "Macro Environment",
                        "Broader external factors completely beyond the business's control (Political, Economic, Social, Technological, Legal, Environmental)."
                    ]
                ],
                "formulas": [
                    [
                        "Strategic Tools",
                        "Micro -> SWOT (Strengths & Weaknesses) | Market -> Porter's 5 Forces | Macro -> PESTLE",
                        "Apply correct tool to matching environment"
                    ]
                ],
                "worked_example": {
                    "problem": "A new competitor opens across the street offering 20% discounts. Name the business environment and the strategic analysis tool to evaluate this challenge.",
                    "steps": [
                        "1. Competitors operate in the Market Environment.",
                        "2. Extent of control: Business has limited influence, not full control.",
                        "3. Porter's Five Forces (Competitive rivalry in the industry) is the appropriate analytical framework."
                    ],
                    "answer": "Market Environment; Porter's Five Forces framework."
                },
                "pitfalls": [
                    "Placing Strengths and Weaknesses in the Macro environment. Strengths and Weaknesses are INTERNAL (Micro); Opportunities and Threats are EXTERNAL.",
                    "Confusing 'control' with 'influence'."
                ],
                "tips": [
                    "Always structure essay answers with Introduction, Body paragraphs with clear headings, and Conclusion to secure maximum format marks (LASO)."
                ]
            }
        ]
    },
    "economics": {
        "subject_name": "Economics",
        "curriculum_overview": "Macroeconomics (Circular Flow, National Accounts), Microeconomics (Market Structures), Economic Pursuits, and Contemporary Issues for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Macroeconomics: The Circular Flow Model",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "The continuous flow of spending, production, and income between the four economic participants: Households, Businesses, Government, and Foreign Sector.",
                "definitions": [
                    [
                        "Injections (J)",
                        "Additions of funds into the domestic circular flow stream: Investment (I) + Government Spending (G) + Exports (X)."
                    ],
                    [
                        "Leakages (L)",
                        "Withdrawals of potential spending from the circular flow stream: Savings (S) + Taxes (T) + Imports (M)."
                    ]
                ],
                "formulas": [
                    [
                        "Gross Domestic Product (GDP)",
                        "GDP = C + I + G + (X - M)",
                        "C = Consumption, I = Investment, G = Government, X = Exports, M = Imports"
                    ],
                    [
                        "Equilibrium Condition",
                        "Injections = Leakages: I + G + X = S + T + M",
                        "Ensures macroeconomic balance"
                    ]
                ],
                "worked_example": {
                    "problem": "Given C = 400, I = 150, G = 120, X = 80, M = 90. Calculate the national income using the expenditure method.",
                    "steps": [
                        "1. Write formula: GDP = C + I + G + (X - M)",
                        "2. Substitute values: GDP = 400 + 150 + 120 + (80 - 90)",
                        "3. Calculate: GDP = 670 + (-10) = 660 billion"
                    ],
                    "answer": "GDP = 660 billion"
                },
                "pitfalls": [
                    "Forgetting that Imports (M) are subtracted from Exports (X) to determine net exports (X - M).",
                    "Confusing factor market (labour, land) with goods/product market."
                ],
                "tips": [
                    "When leakages exceed injections (L > J), national income contracts and economic growth slows down."
                ]
            }
        ]
    },
    "geography": {
        "subject_name": "Geography",
        "curriculum_overview": "Climate and Weather (Mid-latitude & Tropical Cyclones), Geomorphology (Drainage basins, Rivers), Settlement Geography, and Map Skills for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Climatology: Mid-Latitude Cyclones & Cold Fronts",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Low-pressure weather systems in the Southern Hemisphere moving west to east, bringing cold fronts, gale-force winds, and rainfall to the Western Cape in winter.",
                "definitions": [
                    [
                        "Mid-Latitude Cyclone",
                        "A large low-pressure frontal weather system developing between 30\u00b0 and 60\u00b0 latitude along the polar front."
                    ],
                    [
                        "Backing of Wind",
                        "Anti-clockwise change in wind direction in the Southern Hemisphere as a cold front approaches and passes (e.g. NW to SW)."
                    ]
                ],
                "formulas": [
                    [
                        "Coriolis Deflection",
                        "Deflects winds to the LEFT in the Southern Hemisphere",
                        "Responsible for clockwise circulation around low pressure in SA"
                    ]
                ],
                "worked_example": {
                    "problem": "Explain the weather changes experienced in Cape Town as a cold front moves directly overhead.",
                    "steps": [
                        "1. Atmospheric pressure drops to its minimum as the front arrives.",
                        "2. Cumulonimbus clouds develop, producing heavy rainfall and possible thunder.",
                        "3. Temperatures plummet rapidly.",
                        "4. Wind backs from North-Westerly to cold South-Westerly."
                    ],
                    "answer": "Pressure drops, temperature drops, wind backs from NW to SW, and heavy frontal rain falls."
                },
                "pitfalls": [
                    "Drawing cyclonic winds anti-clockwise. In the Southern Hemisphere, low pressure winds rotate CLOCKWISE.",
                    "Confusing mid-latitude cyclones (occur all year, cold front) with tropical cyclones (warm summer oceans, eye present)."
                ],
                "tips": [
                    "Look for the characteristic comma-shaped cloud band on satellite images to identify a mature mid-latitude cyclone."
                ]
            }
        ]
    },
    "history": {
        "subject_name": "History",
        "curriculum_overview": "The Cold War, Independent Africa, Civil Society Protests, The Struggle for Freedom in South Africa, and Globalisation for Grades 10\u201312.",
        "chapters": [
            {
                "title": "The Cold War & The Cuban Missile Crisis (1962)",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Ideological conflict between the capitalist USA and communist USSR, nuclear brinkmanship, and the 13 days of the Cuban Missile Crisis.",
                "definitions": [
                    [
                        "Containment",
                        "The US geopolitical strategic foreign policy under Truman to prevent the spread of communism abroad."
                    ],
                    [
                        "Mutually Assured Destruction (MAD)",
                        "A military doctrine where a full-scale nuclear exchange by two opposing sides results in the complete annihilation of both attacker and defender."
                    ]
                ],
                "formulas": [
                    [
                        "Historiographical Source Analysis",
                        "O-P-V-L: Origin, Purpose, Value, Limitations",
                        "Standard framework for examining historical primary sources"
                    ]
                ],
                "worked_example": {
                    "problem": "How did President John F. Kennedy resolve the Cuban Missile Crisis without triggering nuclear war?",
                    "steps": [
                        "1. Implemented a naval blockade ('quarantine') around Cuba to intercept Soviet supply ships.",
                        "2. Engaged in secret diplomacy with Soviet Premier Nikita Khrushchev.",
                        "3. Agreed publicly not to invade Cuba, and secretly agreed to withdraw US Jupiter missiles from Turkey.",
                        "4. Khrushchev ordered Soviet nuclear missiles dismantled and returned to the USSR."
                    ],
                    "answer": "Instituted a naval quarantine and negotiated a secret missile-swap agreement with Khrushchev."
                },
                "pitfalls": [
                    "Using conversational slang in history essay responses. Essays require formal, academic prose and chronological structure.",
                    "Stating opinions without substantiating evidence from historical documents."
                ],
                "tips": [
                    "Always link every body paragraph back to the question statement (Line of Argument).",
                    "In source evaluation questions, assess who created the source and what bias they might hold."
                ]
            }
        ]
    },
    "maths_lit": {
        "subject_name": "Mathematical Literacy",
        "curriculum_overview": "Numbers & Calculations in Financial Contexts (Tax, Tariffs, Loans), Measurement, Maps & Plans, and Data Handling for Grades 10\u201312.",
        "chapters": [
            {
                "title": "Municipal Water & Electricity Tariffs",
                "grades": [
                    10,
                    11,
                    12
                ],
                "summary": "Understanding stepped (sliding scale) block tariffs where higher consumption brackets are charged at increasing unit rates.",
                "definitions": [
                    [
                        "Stepped Tariff",
                        "A pricing structure where the cost per unit increases as the quantity consumed exceeds designated volume blocks."
                    ],
                    [
                        "Value Added Tax (VAT)",
                        "An indirect tax levied on taxable goods and services in South Africa at a statutory rate of 15%."
                    ]
                ],
                "formulas": [
                    [
                        "VAT Calculation",
                        "VAT Amount = Price Exclusive \u00d7 0.15 | Price Inclusive = Price Exclusive \u00d7 1.15",
                        "To find exclusive from inclusive: Price Inclusive / 1.15"
                    ]
                ],
                "worked_example": {
                    "problem": "Block 1 (0-6 kl): Free. Block 2 (7-20 kl): R15 per kl. Calculate the cost for using 18 kl of water (excluding VAT).",
                    "steps": [
                        "1. First 6 kl is in Block 1: 6 kl \u00d7 R0 = R0.",
                        "2. Remaining water: 18 kl - 6 kl = 12 kl falls in Block 2.",
                        "3. Cost of Block 2: 12 kl \u00d7 R15 = R180.",
                        "4. Total cost = R0 + R180 = R180."
                    ],
                    "answer": "R180.00"
                },
                "pitfalls": [
                    "Multiplying the entire 18 kl by R15. In stepped tariffs, you MUST calculate each block separately!",
                    "Subtracting 15% from a VAT-inclusive amount instead of dividing by 1.15."
                ],
                "tips": [
                    "Always write currency answers to two decimal places (e.g. R180.00, not R180).",
                    "Keep units in every step of your calculation."
                ]
            }
        ]
    },
    "english": {
        "subject_name": "English First Additional & Home Language",
        "curriculum_overview": "Language structures, figures of speech, active/passive voice, direct/indirect reported speech, and critical language awareness for Grades 8\u201312.",
        "chapters": [
            {
                "title": "Figures of Speech & Rhetorical Devices",
                "grades": [
                    8,
                    9,
                    10,
                    11,
                    12
                ],
                "summary": "Identification and analysis of figurative language used by authors and poets to evoke imagery and enhance meaning.",
                "definitions": [
                    [
                        "Metaphor",
                        "A direct figurative comparison stating that one thing IS another without using 'like' or 'as'."
                    ],
                    [
                        "Personification",
                        "Giving human characteristics, thoughts, or emotions to an inanimate object or animal."
                    ],
                    [
                        "Oxymoron",
                        "A figure of speech where two seemingly contradictory terms appear juxtaposed (e.g. 'deafening silence')."
                    ]
                ],
                "formulas": [
                    [
                        "Analysis Framework",
                        "1. Identify technique -> 2. Quote words -> 3. Explain literal meaning -> 4. Explain figurative effect on reader",
                        "Never stop at just naming the figure"
                    ]
                ],
                "worked_example": {
                    "problem": "Identify and explain the figure of speech in: 'The relentless wind howled its grief into the empty night.'",
                    "steps": [
                        "1. Identify figure: Personification.",
                        "2. Words quoted: 'howled its grief'.",
                        "3. Explanation: Grief and howling in sorrow are human emotional responses attributed to the wind.",
                        "4. Effect: Conveys the immense power, sadness, and mournful atmosphere of the stormy night."
                    ],
                    "answer": "Personification: Attributes human weeping/howling to the wind, creating an intense, sorrowful mood."
                },
                "pitfalls": [
                    "Merely naming the figure of speech without explaining its effect or purpose in the passage.",
                    "Confusing a simile (uses 'like' or 'as') with a metaphor."
                ],
                "tips": [
                    "In Paper 1 comprehension, check mark allocation: 2 marks usually requires identification + effect."
                ]
            },
            {
                "title": "Active & Passive Voice Transformations",
                "grades": [
                    8,
                    9,
                    10,
                    11,
                    12
                ],
                "summary": "Transforming sentences between active voice (subject performs action) and passive voice (subject receives action) without altering tense.",
                "definitions": [
                    [
                        "Active Voice",
                        "The subject of the sentence actively performs the action expressed by the verb (e.g. 'The dog chased the ball')."
                    ],
                    [
                        "Passive Voice",
                        "The subject undergoes or receives the action, placing focus on the receiver or outcome (e.g. 'The ball was chased by the dog')."
                    ]
                ],
                "formulas": [
                    [
                        "Passive Voice Formula",
                        "Object + Appropriate tense of 'to be' + Past Participle (V3) + [by Subject]",
                        "Tense MUST NOT change"
                    ]
                ],
                "worked_example": {
                    "problem": "Rewrite in the passive voice: 'The inspector reviewed the financial records.'",
                    "steps": [
                        "1. Identify subject, verb, and object: Subject = 'The inspector', Verb = 'reviewed' (Past simple), Object = 'the financial records' (Plural).",
                        "2. Move object to front: 'The financial records...'",
                        "3. Add past form of 'to be' for plural: 'were'.",
                        "4. Add past participle of verb: 'reviewed'.",
                        "5. Add agent: 'by the inspector'."
                    ],
                    "answer": "The financial records were reviewed by the inspector."
                },
                "pitfalls": [
                    "Altering the tense of the sentence (e.g. turning past simple into present perfect).",
                    "Subject-verb agreement errors (e.g. using 'was' instead of 'were' for plural objects)."
                ],
                "tips": [
                    "Identify the tense of the original verb FIRST before doing anything else."
                ]
            }
        ]
    },
    "life_orientation": {
        "subject_name": "Life Orientation",
        "curriculum_overview": "Development of the Self in Society, Careers and Career Choices, Democracy and Human Rights, and Social and Environmental Responsibility for Grades 8\u201312.",
        "chapters": [
            {
                "title": "Study Skills, Examination Strategies & SMART Goal Setting",
                "grades": [
                    8,
                    9,
                    10,
                    11,
                    12
                ],
                "summary": "Proven revision strategies, study methods (mind mapping, flashcards, active recall), and setting achievable academic goals.",
                "definitions": [
                    [
                        "SMART Goals",
                        "Specific, Measurable, Achievable, Relevant, and Time-bound objectives."
                    ],
                    [
                        "Active Recall",
                        "A learning principle in which the student actively stimulates memory retrieval during the learning process rather than passive reading."
                    ]
                ],
                "formulas": [
                    [
                        "SMART Criteria",
                        "S = Specific | M = Measurable | A = Achievable | R = Relevant | T = Time-bound",
                        "Every academic target must meet all 5 criteria"
                    ]
                ],
                "worked_example": {
                    "problem": "Transform the vague goal 'I want to do better in Maths' into a SMART goal.",
                    "steps": [
                        "1. Specific: Focus on CAPS Maths Paper 1 topics.",
                        "2. Measurable: Aim for a specific target percentage (e.g. increase from 55% to 70%).",
                        "3. Achievable: Complete 3 past DBE exam papers every week.",
                        "4. Relevant: Needed to qualify for a BCom or Engineering degree at university.",
                        "5. Time-bound: By the September Preliminary examinations."
                    ],
                    "answer": "I will achieve 70% in Maths by the September Trial exams by completing 3 past papers per week."
                },
                "pitfalls": [
                    "Giving one-word answers in LO exam papers. Questions asking to 'Evaluate', 'Critically discuss', or 'Recommend' require well-explained sentences with cause and effect.",
                    "Confusing study methods (how you study) with study skills (internal habits)."
                ],
                "tips": [
                    "Use the P-E-E formula in essay questions: Point, Explain, Example."
                ]
            }
        ]
    }
}


# ---------------------------------------------------------
# 1C. JJK champion CURSED NOTES (All Subjects, All Grades)
# ---------------------------------------------------------
JJK_NOTES = {
    "mathematics": {
        "opening": "Alright, ronin. Listen up. Mathematics isn't a school subject. It's the universe's innate domain. Every theorem is a binding vow the cosmos made with itself. You don't 'learn' math — you exorcise ignorance.",
        "sections": [
            {"title": "Domain Expansion: Algebra & Equations", "body": "Isolate the variable. The equal sign is a binding vow: whatever you do to one side, you must do to the other. Break the vow, and the equation collapses. Factorisation is just breaking a complex curse down into its original, simpler components."},
            {"title": "Domain Expansion: Geometry & Pythagoras", "body": "A right-angled triangle is a closed domain. The hypotenuse is the sure-hit — the longest side, always facing the right angle. Pythagoras discovered the binding vow that binds them: a² + b² = c². Master this, and you can calculate the distance between any two points in space."},
            {"title": "Domain Expansion: Trigonometry", "body": "SOH CAH TOA is your cursed technique. Sine, Cosine, and Tangent are the ratios that connect angles to sides. The unit circle is your domain — an infinite cycle of angles that repeat every 360 degrees. Master the wave, and you control the oscillation."}
        ],
        "final_word": "Throughout heaven and earth, only the correctly calculated answer is real. Show your steps, ronin."
    },
    "natural_sciences": {
        "opening": "Alright, ronin. Listen up. Natural Sciences is the study of cursed energy in the physical and living world. Every reaction, every cell, every circuit is a cursed technique in motion.",
        "sections": [
            {"title": "Domain Expansion: Life & Living", "body": "The digestive system is a cursed pipeline. Food enters, enzymes strike, nutrients are absorbed, and waste is egested. Peristalsis is the wave-like cursed energy that pushes it all forward. The stomach is a domain of acid (pH 2) where proteins are dismantled."},
            {"title": "Domain Expansion: Matter & Materials", "body": "Atoms are the building blocks of cursed energy. Protons, neutrons, and electrons are the subatomic curses that bind together. The Periodic Table is your grimoire — every element has a unique cursed technique based on its electron configuration."},
            {"title": "Domain Expansion: Energy & Change", "body": "An electric circuit is a loop of cursed energy. Voltage is the pressure, current is the flow, resistance is the opposition. Ohm's Law (V = I × R) is the binding vow that controls it all. Series circuits share voltage; parallel circuits share current. Master the loop, and you control the power."}
        ],
        "final_word": "The universe's innate domain is biology and physics. Its sure-hit is homeostasis. Keep the balance, ronin."
    },
    "ems": {
        "opening": "Alright, ronin. Listen up. EMS is the study of cursed energy flow — money, resources, and the invisible forces that govern wealth. Every transaction is a binding vow between debit and credit.",
        "sections": [
            {"title": "Domain Expansion: The Accounting Equation", "body": "A = O + L. Assets = Owner's Equity + Liabilities. This is the sure-hit. If your equation doesn't balance, your domain collapses. Every transaction must leave this equation in perfect equilibrium. No exceptions."},
            {"title": "Domain Expansion: Journals & Ledgers", "body": "The Cash Receipts Journal (CRJ) captures money coming in. The Cash Payments Journal (CPJ) captures money going out. Debtors owe you; Creditors are owed by you. DEAD CLIC is your binding vow: Debit Expenses, Assets, Drawings; Credit Liabilities, Income, Capital."},
            {"title": "Domain Expansion: The Economy", "body": "The circular flow model is the domain of macroeconomics. Households provide labour; businesses provide goods. The government taxes and spends. The foreign sector imports and exports. Leakages (Savings, Taxes, Imports) must equal Injections (Investment, Government Spending, Exports). Balance is the goal."}
        ],
        "final_word": "Throughout heaven and earth, every debit has an equal and opposite credit. Balance your books, ronin."
    },
    "social_sciences": {
        "opening": "Alright, ronin. Listen up. Social Sciences is the study of cursed history and cursed geography. Every map is a domain. Every war is a cursed spirit born from human conflict.",
        "sections": [
            {"title": "Domain Expansion: Geography - Mapwork", "body": "Topographic maps are your terrain domains. Contour lines reveal the elevation. Closely packed lines mean a steep slope; widely spaced lines mean a gentle one. The 1:50 000 scale is a binding vow: 1 cm on the map equals 500 meters in the real world. Master the map, and you master the land."},
            {"title": "Domain Expansion: History - Colonialism", "body": "The Scramble for Africa was a cursed invasion. European powers drew straight lines on a map, ignoring kingdoms, cultures, and tribes. The Berlin Conference was the binding vow that sealed Africa's fate. The resistance of the Ashanti, the Zulu, and the Herero is the cursed energy that fought back."},
            {"title": "Domain Expansion: History - Apartheid", "body": "Apartheid was a cursed system of legalised segregation. The Population Registration Act classified every South African by race. The Group Areas Act divided the land. But the resistance — the ANC, the PAC, the students of Soweto — was the reverse cursed technique that healed the nation. Never forget the cost."}
        ],
        "final_word": "Those who forget history are exorcised by it. Those who study it, control the future."
    },
    "technology": {
        "opening": "Alright, ronin. Listen up. Technology is the art of building cursed tools. Every lever, every gear, every circuit is a cursed mechanism that multiplies your power.",
        "sections": [
            {"title": "Domain Expansion: Mechanical Advantage", "body": "FLE 1-2-3 is the sure-hit. Class 1: Fulcrum in the middle (see-saw). Class 2: Load in the middle (wheelbarrow). Class 3: Effort in the middle (tweezers). Mechanical Advantage = Load / Effort. MA > 1 means you've multiplied your force. Use it wisely."},
            {"title": "Domain Expansion: Structures & Triangulation", "body": "A triangle is the strongest shape in the universe. It cannot be deformed without breaking a side. Triangulation is the binding vow of structural engineering — bridges, cranes, and towers all rely on it. A square can collapse; a triangle never yields."},
            {"title": "Domain Expansion: Mechanisms & Gears", "body": "Gears are cursed tools that transfer rotational energy. A gear train can increase speed or torque. A pulley system can lift heavy loads with minimal effort. A crank converts circular motion into linear motion. Every mechanism is a binding vow between input and output."}
        ],
        "final_word": "Throughout heaven and earth, only the well-designed tool is real. Build it, test it, improve it, ronin."
    },
    "physical_sciences": {
        "opening": "Physics isn't a school subject. It's the universe's innate domain. Every law is a binding vow the cosmos made with itself. You don't 'learn' physics — you exorcise ignorance.",
        "sections": [
            {"title": "Domain Expansion: Thermodynamics", "body": "Cursed energy = energy. The First Law is a binding vow: energy cannot be created or destroyed, only converted. Punch a curse? Chemical energy in your muscles becomes kinetic energy, sound, and heat. That heat is residual cursed energy — you can't exorcise it.\n\nEntropy = the curse that never leaves. Second Law: in a closed system, disorder always increases. Reverse Cursed Technique can heal a wound locally, but it doesn't erase entropy — it just pays the cost elsewhere. The universe always collects."},
            {"title": "Domain Expansion: Newton's Cursed Technique", "body": "First Law: A body keeps doing what it's doing unless a force acts. That's not laziness. That's inertia. A ronin standing still is still moving through spacetime.\n\nSecond Law: F = ma. Want to move a curse? Apply force. More mass = more cursed energy required. Yuji's physicals are terrifying because he outputs huge force with efficient motion.\n\nThird Law: Every action has an equal and opposite reaction. Punch a wall, your hand feels it. Black Flash is just perfect timing — landing the impact when cursed energy and physical strike resonate, maximizing impulse."},
            {"title": "Domain Expansion: Limitless / Relativity", "body": "Mass curves spacetime like a Domain Expansion. The Earth isn't 'pulled' by the Sun — it's following the geometry of the Sun's domain. General relativity is just the sure-hit of gravity.\n\nInfinity = Zeno's paradox with cursed energy. Gojo doesn't block you. He divides the distance infinitely: 1/2, 1/4, 1/8... The limit is zero. You never arrive. It's a convergent infinite series used as a barrier.\n\nTime dilation? Near massive objects or at high speed, time slows. If you're in Gojo's domain, your subjective time might feel normal while the outside world ages. That's relativity."},
            {"title": "Domain Expansion: Quantum Mechanics", "body": "Particles aren't tiny curses. They're wavefunctions — probability clouds. Until you measure them, they're in superposition, like Megumi's shadows holding many possibilities at once. Measurement collapses the state.\n\nTunneling: A particle leaks through a barrier it shouldn't have enough energy to cross. That's how stars fuse and how radioactive decay happens. It's cursed energy slipping through a closed domain.\n\nEntanglement = a binding vow between particles. Measure one, and you instantly know the other's state. No message travels faster than light — the correlation was baked in from the start."},
            {"title": "Domain Expansion: Electromagnetism", "body": "Kashimo's lightning. Charge is polarity. Opposite charges attract, same charges repel. Current is electron flow. Lightning is dielectric breakdown: the electric field gets so strong that air becomes plasma and conducts. Light is an electromagnetic wave. Colour is frequency."},
            {"title": "Domain Expansion: Waves & Resonance", "body": "Nobara's Straw Doll Technique is resonance. Push a swing at its natural frequency and amplitude grows. Black Flash is a 0.000001-second window where your cursed energy hits in phase with the physical blow. Maximum energy transfer. Miss the window, and it's just a normal hit."},
            {"title": "Domain Expansion: Nuclear & Particle", "body": "E = mc². Mass is just incredibly condensed energy. Nuclear reactions convert a tiny bit of mass into enormous energy. Hollow Purple is basically 'imaginary mass' erasing matter — physics-flavoured annihilation. Matter-antimatter does the same: mass becomes pure energy."},
            {"title": "Domain Expansion: Conservation Laws", "body": "Binding vows = symmetries. Noether's theorem: every symmetry gives a conservation law. Time symmetry → energy conservation. Space symmetry → momentum conservation. The universe made a binding vow with itself: because the laws don't change over time, energy is conserved."}
        ],
        "final_word": "The universe's innate domain is math. Its sure-hit is entropy. There is no Reverse Cursed Technique for the heat death of the universe. Throughout heaven and earth, you alone are made of quantized fields."
    },
    "life_sciences": {
        "opening": "Alright, ronin. Listen up. Life Sciences is the study of the cursed code of life. DNA is a binding vow written in base pairs. Every cell is a domain of cursed energy in motion.",
        "sections": [
            {"title": "Domain Expansion: DNA & Protein Synthesis", "body": "DNA is the cursed scroll of life. Transcription copies the code onto mRNA in the nucleus. Translation decodes it at the ribosome into proteins. Base pairing is the binding vow: A pairs with T, C pairs with G. In RNA, Uracil replaces Thymine. Break the vow, and the protein mutates."},
            {"title": "Domain Expansion: Genetics & Inheritance", "body": "A Punnett square is a domain of probability. Mendel's laws are binding vows of inheritance. Monohybrid crosses follow the 3:1 ratio. Sex-linked disorders are carried on the X chromosome — a cursed trait passed from mother to son. Master the square, and you predict the future."},
            {"title": "Domain Expansion: Evolution", "body": "Natural selection is the ultimate sure-hit. Organisms with favourable traits survive and reproduce. Organisms with unfavourable traits are exorcised. Over millions of years, this cursed pressure shapes entire species. Darwin discovered the binding vow of survival: adapt, or die."}
        ],
        "final_word": "Throughout heaven and earth, only natural selection is absolute. Adapt, ronin, or be exorcised by time."
    },
    "accounting": {
        "opening": "Alright, ronin. Listen up. Accounting is the cursed ledger of every financial soul. Every transaction is a binding vow between debit and credit, recorded for eternity.",
        "sections": [
            {"title": "Domain Expansion: General Ledger", "body": "The General Ledger is your domain. Every account is a T-shape. Debits on the left, Credits on the right. Assets increase on the debit side. Liabilities increase on the credit side. The trial balance is the sure-hit — if it doesn't balance, your domain collapses."},
            {"title": "Domain Expansion: Bank Reconciliation", "body": "The bank statement is a cursed scroll. The business's records are another. They don't always match. Outstanding deposits, uncredited cheques, bank charges, interest — these are the cursed discrepancies you must exorcise. Reconcile them both, and the truth emerges."},
            {"title": "Domain Expansion: Financial Statements", "body": "The Income Statement is the domain of profit and loss. The Balance Sheet is the domain of assets and liabilities. The Cash Flow Statement is the domain of liquidity. Together, they paint a complete picture of the business's cursed financial soul. Master them all, and you master the business."}
        ],
        "final_word": "Throughout heaven and earth, only the balanced ledger is real. Check your debits and credits, ronin."
    },
    "business_studies": {
        "opening": "Alright, ronin. Listen up. Business Studies is the study of cursed business environments. Every decision a CEO makes is a cursed technique that ripples through micro, market, and macro domains.",
        "sections": [
            {"title": "Domain Expansion: The Three Environments", "body": "The Micro environment is your internal domain — Vision, Mission, and the 8 business functions. The Market environment is your competitive domain — Customers, Competitors, Suppliers. The Macro environment is the external cursed domain — PESTLE factors beyond your control. Know your domain, and you know your power."},
            {"title": "Domain Expansion: SWOT & Strategy", "body": "SWOT is your sure-hit. Strengths and Weaknesses are internal cursed energy you control. Opportunities and Threats are external cursed spirits you must adapt to. Porter's Five Forces is your reverse cursed technique — analyse the competitive landscape to neutralise threats. Strategy is survival."},
            {"title": "Domain Expansion: Business Operations", "body": "Operations management is the cursed art of efficiency. Logistics, quality control, and supply chain management are the binding vows that keep the business running. Break the chain, and the whole operation collapses. Master the flow, and you master the business."}
        ],
        "final_word": "Throughout heaven and earth, only adaptive businesses survive. Adapt or be exorcised by change, ronin."
    },
    "economics": {
        "opening": "Alright, ronin. Listen up. Economics is the study of cursed energy flow — markets, inflation, and national wealth. Every transaction is a binding vow between buyer and seller.",
        "sections": [
            {"title": "Domain Expansion: Circular Flow", "body": "The circular flow model is the domain of macroeconomics. Households provide labour; businesses provide goods. Government taxes and spends. The foreign sector imports and exports. Leakages (Savings, Taxes, Imports) must equal Injections (Investment, Government Spending, Exports). Balance is the goal."},
            {"title": "Domain Expansion: Supply & Demand", "body": "The demand curve slopes downward: as price falls, quantity demanded rises. The supply curve slopes upward: as price rises, quantity supplied rises. Where they intersect is market equilibrium — the sure-hit of every free market. Price controls break the vow; the market always finds a way."},
            {"title": "Domain Expansion: Macroeconomics", "body": "GDP = C + I + G + (X - M). This is the cursed equation of national income. Business cycles — expansion, peak, recession, trough — are the waves of economic cursed energy. Inflation erodes purchasing power. Unemployment wastes human potential. Master the macro domain, and you understand the economy."}
        ],
        "final_word": "Throughout heaven and earth, only supply and demand are absolute. The market never sleeps, ronin."
    },
    "geography": {
        "opening": "Alright, ronin. Listen up. Geography is the study of cursed earth and cursed sky. Every climate, every mountain, every river is a domain shaped by binding vows of nature.",
        "sections": [
            {"title": "Domain Expansion: Climatology", "body": "Mid-latitude cyclones move WEST to EAST in the Southern Hemisphere. Clockwise circulation around low pressure. Cold fronts bring rain and temperature drops. Tropical cyclones form over warm oceans (26°C+) and have a calm eye at the centre. The atmosphere is a domain of pressure and wind — master it, and you predict the weather."},
            {"title": "Domain Expansion: Geomorphology", "body": "The Earth's crust is a domain of rock and time. Plate tectonics move continents. Weathering breaks rock into soil. Rivers carve valleys and deposit sediment. Drainage basins are the cursed watersheds that collect all water in a region. The land is always changing — nothing is permanent."},
            {"title": "Domain Expansion: Mapwork & GIS", "body": "Topographic maps are your terrain domains. Contour lines reveal elevation. The 1:50 000 scale is a binding vow: 1 cm = 500 m. Gradient is the slope. Cross-sections reveal the vertical profile. GIS layers information like cursed techniques stacked on a single map. Read the land, ronin."}
        ],
        "final_word": "Throughout heaven and earth, only the topography is real. The land remembers everything."
    },
    "history": {
        "opening": "Alright, ronin. Listen up. History is the study of cursed memory. Every war, every revolution, every struggle is a cursed spirit born from human choices. You don't 'learn' history — you exorcise the past.",
        "sections": [
            {"title": "Domain Expansion: The Cold War", "body": "The Cold War was a domain of ideological cursed energy. Capitalism (USA) vs Communism (USSR). Nuclear brinkmanship. The Cuban Missile Crisis (1962) was the closest the world came to annihilation — 13 days of pure tension. MAD (Mutually Assured Destruction) was the binding vow that kept the peace."},
            {"title": "Domain Expansion: Independent Africa", "body": "The Scramble for Africa was a cursed invasion. The Berlin Conference (1884) drew straight lines on a map, ignoring kingdoms and cultures. The resistance of the Ashanti, the Zulu, and the Herero is the cursed energy that fought back. Independence movements in Ghana, Congo, and Tanzania are the reverse cursed technique that healed the wounds."},
            {"title": "Domain Expansion: Apartheid & Resistance", "body": "Apartheid was a cursed system of legalised segregation. The Population Registration Act classified every South African by race. The Group Areas Act divided the land. But the resistance — the ANC, the PAC, the students of Soweto — was the reverse cursed technique that healed the nation. Never forget the cost of freedom."}
        ],
        "final_word": "Those who forget history are exorcised by it. Those who study it, control the future. Never forget, ronin."
    },
    "maths_lit": {
        "opening": "Alright, ronin. Listen up. Mathematical Literacy is the study of cursed real-world mathematics. Every tariff, every loan, every tax bracket is a cursed technique you must master to survive in the modern world.",
        "sections": [
            {"title": "Domain Expansion: Municipal Tariffs", "body": "Stepped tariffs are the sure-hit. Calculate each block separately. Block 1: first 10 kL at R15/kL. Block 2: next 10 kL at R25/kL. Block 3: remaining at R40/kL. NEVER multiply the whole usage by the top rate. Break the blocks, exorcise the cost."},
            {"title": "Domain Expansion: Income Tax & SARS", "body": "SARS is the cursed tax domain. Tax brackets are binding vows: the more you earn, the higher the percentage. Rebates reduce your liability. Medical credits reduce it further. Calculate your taxable income, apply the bracket, subtract the rebate. The taxman always collects."},
            {"title": "Domain Expansion: Measurement & Scale", "body": "Area, perimeter, volume — these are the spatial domains of measurement. Floor plans are scaled drawings. 1:100 means 1 cm on paper = 100 cm in real life. Convert units carefully: mm to cm, cm to m, m to km. The binding vow of measurement is precision. Master the scale, and you master the space."}
        ],
        "final_word": "Throughout heaven and earth, only correctly calculated money is real. Count every rand, ronin."
    },
    "english": {
        "opening": "Alright, ronin. Listen up. English is the study of cursed words. Every metaphor, every simile, every rhetorical device is a cursed technique that shapes reality through language.",
        "sections": [
            {"title": "Domain Expansion: Figures of Speech", "body": "A metaphor is a direct comparison — one thing IS another. A simile uses 'like' or 'as'. Personification gives human traits to non-human things. Hyperbole exaggerates for effect. Oxymoron combines contradictions. Identify the technique, quote the words, explain the effect. That is the sure-hit of literature analysis."},
            {"title": "Domain Expansion: Active & Passive Voice", "body": "In active voice, the subject performs the action: 'The dog chased the ball.' In passive voice, the subject receives the action: 'The ball was chased by the dog.' Passive voice is the reverse cursed technique — it shifts the focus and hides the agent. Transform between them without changing the tense. That is the binding vow of grammar."},
            {"title": "Domain Expansion: Visual Literacy", "body": "Cartoons, advertisements, and memes are visual cursed techniques. They use satire, irony, and symbolism to convey meaning. Analyse the body language, the speech bubbles, and the colours. Every detail is intentional. Every frame is a binding vow between the artist and the viewer. Read the image, ronin."}
        ],
        "final_word": "Throughout heaven and earth, only the well-argued essay is real. Write with precision, ronin."
    },
    "life_orientation": {
        "opening": "Alright, ronin. Listen up. Life Orientation is the study of cursed self-mastery. Every goal, every decision, every relationship is a binding vow with your future self.",
        "sections": [
            {"title": "Domain Expansion: SMART Goals", "body": "SMART is the sure-hit: Specific, Measurable, Achievable, Relevant, Time-bound. Every academic goal must satisfy all five criteria. Break the vow, and your goal is just a wish. Master the framework, and you control your destiny."},
            {"title": "Domain Expansion: Peer Pressure", "body": "Peer pressure is a cursed spirit that attacks your decision-making. It whispers: 'Everyone is doing it.' The reverse cursed technique is refusal. The binding vow is your values. You don't have to follow the crowd. You decide who you are. Stand firm, ronin."},
            {"title": "Domain Expansion: Study Skills", "body": "Active recall is the sure-hit. Don't just read — test yourself. Spaced repetition is the binding vow: review the material at increasing intervals. Mind maps, flashcards, and past papers are your cursed tools. Master the method, and you master the exam."}
        ],
        "final_word": "Throughout heaven and earth, only the self-aware ronin is free. Master yourself, ronin."
    }
}
# Helper: Get JJK-toned notes for any subject
def get_jjk_notes_for_subject(subject_id):
    return JJK_NOTES.get(subject_id, None)
# ---------------------------------------------------------
# 2. AESTHETIC THEMES & CUSTOM CSS
# ---------------------------------------------------------
AESTHETICS = {
    "cyberpunk_neon": {
        "name": "⚡ Cyberpunk 2099 (Neon Blue, Purple & Pink)",
        "bg": "#070814",
        "card": "#0c0d24",
        "text": "#e0f7ff",
        "accent": "#00f0ff",
        "secondary": "#b026ff",
        "pink": "#ff007f",
        "border": "#00f0ff",
        "glow": "0 0 15px rgba(0,240,255,0.4), 0 0 30px rgba(176,38,255,0.25)"
    },
    "midnight": {
        "name": "🌙 Midnight LockIn",
        "bg": "#090d16",
        "card": "#131b2e",
        "text": "#e2e8f0",
        "accent": "#6366f1",
        "secondary": "#818cf8",
        "pink": "#ec4899",
        "border": "rgba(99,102,241,0.3)",
        "glow": "0 0 15px rgba(99,102,241,0.2)"
    },
        "coquette_blush": {
        "name": "🌸 Coquette Rose & Lilac",
        "bg": "#fff5f8",
        "card": "#fffafc",
        "text": "#5c2e45",
        "accent": "#e8a0b8",
        "secondary": "#d4b8e8",
        "pink": "#f4b8cc",
        "border": "rgba(232,160,184,0.45)",
        "glow": "0 0 18px rgba(244,184,204,0.45), 0 0 30px rgba(212,184,232,0.3)"
    },
        "dark_academia": {
        "name": "📜 Dark Academia Scholar",
        "bg": "#14100b",
        "card": "#241c14",
        "text": "#e8dcc4",
        "accent": "#c8944a",
        "secondary": "#8a6d4b",
        "pink": "#b8860b",
        "border": "rgba(200,148,74,0.35)",
        "glow": "0 0 14px rgba(200,148,74,0.18)"
    },
        "lofi_sunset": {
        "name": "🌆 Lofi Sunset Chill",
        "bg": "#1a1228",
        "card": "#2a1d3d",
        "text": "#fde8d5",
        "accent": "#f97316",
        "secondary": "#ec4899",
        "pink": "#fb7185",
        "border": "rgba(249,115,22,0.45)",
        "glow": "0 0 20px rgba(249,115,22,0.45), 0 0 35px rgba(236,72,153,0.35)"
    },
    "sage_matcha": {
        "name": "🍵 Sage Matcha Calm",
        "bg": "#f4f7f4",
        "card": "#ffffff",
        "text": "#1c2b1e",
        "accent": "#15803d",
        "secondary": "#10b981",
        "pink": "#059669",
        "border": "rgba(21,128,61,0.25)",
        "glow": "0 0 12px rgba(16,185,129,0.15)"
    },
    "dracula_violet": {
        "name": "🧛 Dracula Violet",
        "bg": "#1e1f29",
        "card": "#282a36",
        "text": "#f8f8f2",
        "accent": "#bd93f9",
        "secondary": "#ff79c6",
        "pink": "#ff79c6",
        "border": "rgba(189,147,249,0.4)",
        "glow": "0 0 16px rgba(189,147,249,0.25)"
    },
    "varsity_gold": {
        "name": "🏆 Varsity Gold",
        "bg": "#0b1726",
        "card": "#14253d",
        "text": "#f8fafc",
        "accent": "#eab308",
        "secondary": "#38bdf8",
        "pink": "#f59e0b",
        "border": "rgba(234,179,8,0.35)",
        "glow": "0 0 16px rgba(234,179,8,0.2)"
    },
          "matrix_hacker": {
        "name": "🔵 Cyber Hacker",
        "bg": "#000814",
        "card": "#001a2e",
        "text": "#00e5ff",
        "accent": "#00e5ff",
        "secondary": "#0099ff",
        "pink": "#00d4ff",
        "border": "rgba(0,229,255,0.5)",
        "glow": "0 0 20px rgba(0,229,255,0.7), 0 0 40px rgba(0,229,255,0.35)"
    },  
           "jjk_champion": {
        "name": "⚔️ JJK champion",
        "bg": "#0a0106",
        "card": "#160822",
        "text": "#e0e0e8",
        "accent": "#4e1782",
        "secondary": "#7a0f0f",
        "pink": "#4d0991",
        "border": "rgba(220,38,38,0.5)",
        "glow": "0 0 20px rgba(220,38,38,0.5), 0 0 40px rgba(168,85,247,0.35)"
    }     
}
def _generate_matrix_rain_html():
    """Generate a random matrix rain effect with falling 0s and 1s."""
    import random as _r
    cols = []
    for i in range(20):
        # Vertical column of random 0s and 1s
        chars = "<br>".join(_r.choice(["0", "1"]) for _ in range(30))
        left = (i * 5) + _r.randint(0, 3)
        duration = _r.uniform(6, 14)
        delay = -_r.uniform(0, 14)  # negative so they're mid-fall at load
        opacity = _r.uniform(0.15, 0.45)
        cols.append(
            f'<div class="matrix-col" style="left:{left}%; '
            f'animation-duration:{duration}s; '
            f'animation-delay:{delay}s; '
            f'opacity:{opacity};">{chars}</div>'
        )
    return "<div class='matrix-rain-bg'>" + "".join(cols) + "</div>"
# ==================== MATH ART GENERATORS ====================
def generate_mandala(seed=1, petals=12, layers=4, size=400):
    """Rotational symmetry art — teaches angles + symmetry."""
    import random as _r
    _r.seed(seed)
    cx, cy = size // 2, size // 2
    colors = ["#00f0ff", "#b026ff", "#ff007f", "#facc15", "#10b981", "#f97316"]

    svg = f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="background:#0a0a14;border-radius:16px;width:100%;max-width:480px;">'

    # Guide circles
    for r in range(40, size // 2, 40):
        svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(100,200,255,0.08)" stroke-width="1"/>'

    # Layers of petals
    for layer in range(layers):
        radius = 55 + layer * 40
        num_petals = petals + layer * 2
        color = colors[layer % len(colors)]

        for i in range(num_petals):
            angle = (2 * math.pi / num_petals) * i + layer * 0.3
            x1 = cx + radius * math.cos(angle)
            y1 = cy + radius * math.sin(angle)
            petal_r = _r.randint(8, 18)

            svg += f'<line x1="{cx}" y1="{cy}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{color}" stroke-width="0.6" opacity="0.3"/>'
            svg += f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="{petal_r}" fill="none" stroke="{color}" stroke-width="1.8" opacity="0.75"/>'
            svg += f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="{petal_r * 0.4:.1f}" fill="{color}" opacity="0.5"/>'

    # Center jewel
    svg += f'<circle cx="{cx}" cy="{cy}" r="22" fill="none" stroke="#facc15" stroke-width="2.5"/>'
    svg += f'<circle cx="{cx}" cy="{cy}" r="10" fill="#facc15" opacity="0.9"/>'
    svg += '</svg>'
    return svg


def generate_spirograph(seed=1, R=100, r=30, d=60, size=400, points=800):
    """Hypotrochoid curve — teaches parametric equations."""
    import random as _r
    _r.seed(seed)
    cx, cy = size // 2, size // 2
    colors = ["#00e5ff", "#a855f7", "#ec4899", "#f97316"]

    svg = f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="background:#0a0a14;border-radius:16px;width:100%;max-width:480px;">'

    # Draw the main curve
    for layer in range(4):
        color = colors[layer % len(colors)]
        offset = layer * 0.5
        pts = []
        for i in range(points + 1):
            t = (i / points) * (2 * math.pi * 8)
            x = cx + (R - r) * math.cos(t) + d * math.cos(((R - r) / r) * t + offset)
            y = cy + (R - r) * math.sin(t) - d * math.sin(((R - r) / r) * t + offset)
            pts.append(f"{x:.1f},{y:.1f}")

        svg += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.6"/>'

    svg += '</svg>'
    return svg


def generate_fractal_tree(seed=1, depth=8, size=400):
    """Recursive branching — teaches recursion + biology patterns."""
    import random as _r
    _r.seed(seed)

    cx = size // 2
    cy = size - 20
    svg = f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="background:linear-gradient(180deg,#0a0a1e 0%,#1a0f2e 100%);border-radius:16px;width:100%;max-width:480px;">'

    def draw_branch(x, y, angle, length, thickness, d):
        if d <= 0 or length < 3:
            # Leaf at the tip
            svg_leaf = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{_r.uniform(1.5, 3):.1f}" fill="#10b981" opacity="0.7"/>'
            return svg_leaf

        x2 = x + length * math.cos(angle)
        y2 = y + length * math.sin(angle)

        # Color shifts from brown (trunk) to green (tips)
        ratio = d / depth
        r_col = int(120 * (1 - ratio) + 30 * ratio)
        g_col = int(70 * (1 - ratio) + 180 * ratio)
        b_col = int(40 * (1 - ratio) + 100 * ratio)
        color = f"rgb({r_col},{g_col},{b_col})"

        result = f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{thickness:.1f}" stroke-linecap="round"/>'

        # Recursive branches — teach recursion here!
        branch_angle = _r.uniform(0.3, 0.6)
        new_length = length * _r.uniform(0.65, 0.78)

        result += draw_branch(x2, y2, angle - branch_angle, new_length, thickness * 0.7, d - 1)
        result += draw_branch(x2, y2, angle + branch_angle, new_length, thickness * 0.7, d - 1)

        return result

    svg += draw_branch(cx, cy, -math.pi / 2, 80, 8, depth)
    svg += '</svg>'
    return svg


def generate_sine_wave(seed=1, waves=3, amplitude=60, size=400, points=400):
    """Trig visualization — teaches sine/cosine + waves."""
    import random as _r
    _r.seed(seed)
    cx = size // 2
    cy = size // 2

    svg = f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" style="background:#0a0a14;border-radius:16px;width:100%;max-width:480px;">'

    # Grid
    for i in range(0, size, 40):
        svg += f'<line x1="{i}" y1="0" x2="{i}" y2="{size}" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'
        svg += f'<line x1="0" y1="{i}" x2="{size}" y2="{i}" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'

    # Axes
    svg += f'<line x1="0" y1="{cy}" x2="{size}" y2="{cy}" stroke="#64748b" stroke-width="1.5"/>'
    svg += f'<line x1="{cx}" y1="0" x2="{cx}" y2="{size}" stroke="#64748b" stroke-width="1.5"/>'

    # Multiple sine waves with different colors
    colors = ["#00e5ff", "#a855f7", "#ec4899", "#facc15"]
    for w in range(waves):
        color = colors[w % len(colors)]
        freq = 1 + w * 0.7
        phase = _r.uniform(0, 2 * math.pi)
        pts = []
        for i in range(points + 1):
            x = (i / points) * size
            y = cy - amplitude * math.sin((i / points) * 2 * math.pi * freq + phase)
            pts.append(f"{x:.1f},{y:.1f}")
        svg += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" opacity="0.85"/>'

    svg += '</svg>'
    return svg


# ==================== END MATH ART ====================

def inject_theme_css(theme_key):
    """Inject rich visual styling aligned with the selected aesthetic theme."""
    t = AESTHETICS.get(theme_key, AESTHETICS["cyberpunk_neon"])
    is_cyber = (theme_key == "cyberpunk_neon")
    is_jjk = (theme_key == "jjk_champion")
    is_coquette = (theme_key == "coquette_blush")
    is_matrix = (theme_key == "matrix_hacker")
    is_lofi = (theme_key == "lofi_sunset")
    if is_jjk:
            extra_css = """
        /* ⚔️ JJK champion — Cursed Energy Domain (Red + Purple + Silver) */
        .stApp {
            background-color: #0a0106 !important;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(220,38,38,0.35), transparent 45%),
                radial-gradient(circle at 85% 85%, rgba(168,85,247,0.40), transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(220,38,38,0.08), transparent 60%),
                linear-gradient(rgba(220,38,38,0.10) 1px, transparent 1px),
                linear-gradient(90deg, rgba(168,85,247,0.10) 1px, transparent 1px) !important;
            background-size: 100% 100%, 100% 100%, 100% 100%, 40px 40px, 40px 40px !important;
            background-attachment: fixed !important;
            color: #e0e0e8 !important;
        }
        /* All text elements — silver-white */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
        .stApp [data-testid="stMarkdownContainer"] {
            color: #e0e0e8;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a0410 0%, #0d0206 50%, #12141c 100%) !important;
            border-right: 2px solid #dc2626 !important;
            box-shadow: 0 0 30px rgba(220,38,38,0.5) !important;
        }
        section[data-testid="stSidebar"] * {
            color: #e0e0e8 !important;
        }
        div[data-testid="stExpander"], div[data-testid="stForm"] {
            background: linear-gradient(135deg, #1a0410 0%, #12141c 50%, #0d0206 100%) !important;
            border-radius: 14px !important;
            border: 1.5px solid #dc2626 !important;
            box-shadow: 0 0 20px rgba(220,38,38,0.55), inset 0 0 25px rgba(168,85,247,0.12) !important;
        }
        .stButton>button {
            border-radius: 12px !important;
            font-weight: 800 !important;
            background: linear-gradient(135deg, #dc2626 0%, #7f1d1d 40%, #a855f7 100%) !important;
            color: #ffffff !important;
            border: none !important;
            text-shadow: 0 1px 3px rgba(0,0,0,0.9) !important;
            box-shadow: 0 0 18px rgba(220,38,38,0.75), 0 0 30px rgba(168,85,247,0.45) !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 0 30px rgba(220,38,38,1), 0 0 50px rgba(168,85,247,0.7) !important;
        }
        /* Headers — RED with purple glow (this is the key change) */
        .stApp h1, .stApp h2, .stApp h3 {
            color: #dc2626 !important;
            text-shadow: 0 0 18px rgba(220,38,38,0.8), 0 0 35px rgba(168,85,247,0.4) !important;
            letter-spacing: 0.5px !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: transparent !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(22,4,16,0.8) !important;
            border: 1px solid rgba(220,38,38,0.5) !important;
            border-radius: 10px 10px 0 0 !important;
            color: #e0e0e8 !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #dc2626, #a855f7) !important;
            color: #ffffff !important;
            box-shadow: 0 0 18px rgba(220,38,38,0.7) !important;
        }
        span[data-testid="stMetricValue"] {
            color: #dc2626 !important;
            text-shadow: 0 0 14px rgba(220,38,38,0.8) !important;
        }
        hr {
            border-color: rgba(220,38,38,0.3) !important;
        }
        div[data-testid="stExpander"] summary {
            color: #f5f5f7 !important;
            text-shadow: 0 0 8px rgba(220,38,38,0.5) !important;
        }
        """    
    elif is_lofi:
        extra_css = """
        /* 🌆 Lofi Sunset — warm orange fading into deep purple twilight */
        .stApp {
            background-color: #1a1228 !important;
            background-image: 
                radial-gradient(circle at 20% 15%, rgba(249,115,22,0.28), transparent 50%),
                radial-gradient(circle at 80% 85%, rgba(236,72,153,0.30), transparent 55%),
                radial-gradient(circle at 60% 40%, rgba(168,85,247,0.22), transparent 60%),
                linear-gradient(160deg, #1a1228 0%, #2a1a3a 50%, #1f1528 100%) !important;
            background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100% !important;
            background-attachment: fixed !important;
            color: #fde8d5 !important;
        }

        /* Warm cream text — like sunset light on paper */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
        .stApp [data-testid="stMarkdownContainer"] {
            color: #fde8d5;
        }

        /* Sidebar with sunset-sky vertical gradient */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2a1a3a 0%, #1f1528 60%, #251638 100%) !important;
            border-right: 2px solid rgba(249,115,22,0.5) !important;
            box-shadow: 0 0 30px rgba(249,115,22,0.35) !important;
        }
        section[data-testid="stSidebar"] * {
            color: #fde8d5 !important;
        }

        /* Cards with warm-to-pink gradient */
        div[data-testid="stExpander"], div[data-testid="stForm"] {
            background: linear-gradient(135deg, #2a1d3d 0%, #251638 50%, #2a1d3d 100%) !important;
            border-radius: 16px !important;
            border: 1.5px solid rgba(249,115,22,0.45) !important;
            box-shadow: 0 4px 25px rgba(249,115,22,0.3), 0 0 35px rgba(236,72,153,0.2), inset 0 0 30px rgba(168,85,247,0.1) !important;
        }

        /* Buttons — sunset gradient from orange to pink to purple */
        .stButton>button {
            border-radius: 14px !important;
            font-weight: 700 !important;
            background: linear-gradient(135deg, #f97316 0%, #fb7185 40%, #ec4899 75%, #a855f7 100%) !important;
            color: #ffffff !important;
            border: none !important;
            text-shadow: 0 1px 3px rgba(0,0,0,0.5) !important;
            box-shadow: 0 0 22px rgba(249,115,22,0.6), 0 0 38px rgba(236,72,153,0.45) !important;
            transition: all 0.25s ease !important;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 0 32px rgba(249,115,22,0.9), 0 0 55px rgba(236,72,153,0.7) !important;
        }

        /* Headers — warm orange with pink-purple halo */
        .stApp h1, .stApp h2, .stApp h3 {
            color: #fb923c !important;
            text-shadow: 0 0 18px rgba(249,115,22,0.8), 0 0 35px rgba(236,72,153,0.5), 0 0 55px rgba(168,85,247,0.3) !important;
            letter-spacing: 0.5px !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: transparent !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(42,29,61,0.7) !important;
            border: 1px solid rgba(249,115,22,0.4) !important;
            border-radius: 12px 12px 0 0 !important;
            color: #fde8d5 !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #f97316, #ec4899, #a855f7) !important;
            color: #ffffff !important;
            box-shadow: 0 0 22px rgba(249,115,22,0.7), 0 0 30px rgba(236,72,153,0.5) !important;
        }

        /* Metrics — warm orange glow */
        span[data-testid="stMetricValue"] {
            color: #fb923c !important;
            text-shadow: 0 0 15px rgba(249,115,22,0.8), 0 0 25px rgba(236,72,153,0.5) !important;
        }

        hr {
            border-color: rgba(249,115,22,0.3) !important;
        }

        /* Expander summary */
        div[data-testid="stExpander"] summary {
            color: #fde8d5 !important;
            text-shadow: 0 0 8px rgba(249,115,22,0.6) !important;
        }

        /* Progress bars — sunset gradient */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #f97316, #fb7185, #ec4899, #a855f7) !important;
            box-shadow: 0 0 15px rgba(249,115,22,0.6) !important;
        }
        """
    elif is_matrix:
        matrix_html = _generate_matrix_rain_html()
        extra_css = f"""
        <style>
        /* 🔵 Cyber Hacker — falling 0s and 1s */
        @keyframes matrixFall {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(100vh); }}
        }}

        body, html {{
            background-color: #000814 !important;
        }}
        .stApp {{
            background-color: transparent !important;
            color: #00e5ff !important;
        }}

        .matrix-rain-bg {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            pointer-events: none;
            z-index: 0;
        }}
        .matrix-col {{
            position: absolute;
            top: -100vh;
            font-family: 'Courier New', monospace;
            font-size: 15px;
            line-height: 1.3;
            color: #00e5ff;
            text-shadow: 0 0 5px #00e5ff, 0 0 10px #00e5ff, 0 0 15px #00e5ff;
            white-space: nowrap;
            animation: matrixFall linear infinite;
            pointer-events: none;
        }}

        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
        .stApp [data-testid="stMarkdownContainer"] {{
            color: #00e5ff;
            font-family: 'Courier New', monospace;
        }}

        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #001a2e 0%, #000814 100%) !important;
            border-right: 2px solid #00e5ff !important;
            box-shadow: 0 0 30px rgba(0,229,255,0.6) !important;
            position: relative;
            z-index: 2;
        }}
        section[data-testid="stSidebar"] * {{
            color: #00e5ff !important;
            font-family: 'Courier New', monospace !important;
        }}

        div[data-testid="stExpander"], div[data-testid="stForm"] {{
            background: rgba(0, 15, 30, 0.85) !important;
            border-radius: 4px !important;
            border: 1.5px solid #00e5ff !important;
            box-shadow: 0 0 20px rgba(0,229,255,0.5), inset 0 0 20px rgba(0,229,255,0.08) !important;
        }}

        .stButton>button {{
            border-radius: 4px !important;
            font-weight: 700 !important;
            background: #000814 !important;
            color: #00e5ff !important;
            border: 1.5px solid #00e5ff !important;
            text-shadow: 0 0 5px #00e5ff !important;
            box-shadow: 0 0 15px rgba(0,229,255,0.6), inset 0 0 10px rgba(0,229,255,0.15) !important;
            font-family: 'Courier New', monospace !important;
            transition: all 0.2s ease !important;
        }}
        .stButton>button:hover {{
            background: #00e5ff !important;
            color: #000814 !important;
            box-shadow: 0 0 30px rgba(0,229,255,1), 0 0 45px rgba(0,229,255,0.7) !important;
        }}

        .stApp h1, .stApp h2, .stApp h3 {{
            color: #00d4ff !important;
            text-shadow: 0 0 15px #00e5ff, 0 0 30px #00e5ff, 0 0 45px #00e5ff !important;
            letter-spacing: 1px !important;
        }}

        .stTabs [data-baseweb="tab"] {{
            background: rgba(0,20,46,0.8) !important;
            border: 1px solid #00e5ff !important;
            border-radius: 4px 4px 0 0 !important;
            color: #00e5ff !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: #00e5ff !important;
            color: #000814 !important;
            box-shadow: 0 0 20px rgba(0,229,255,0.9) !important;
        }}

        span[data-testid="stMetricValue"] {{
            color: #00d4ff !important;
            text-shadow: 0 0 15px #00e5ff, 0 0 25px #00e5ff !important;
        }}

        hr {{
            border-color: rgba(0,229,255,0.4) !important;
        }}

        div[data-testid="stExpander"] summary {{
            color: #00e5ff !important;
            text-shadow: 0 0 8px #00e5ff !important;
        }}

        .stProgress > div > div > div > div {{
            background: #00e5ff !important;
            box-shadow: 0 0 15px #00e5ff !important;
        }}

        input, textarea {{
            background: rgba(0,20,46,0.8) !important;
            color: #00e5ff !important;
            border: 1px solid #00e5ff !important;
            font-family: 'Courier New', monospace !important;
        }}

        /* Push main content above the rain */
        .main, section.main, [data-testid="stMain"], .block-container {{
            position: relative;
            z-index: 2;
        }}
        </style>
        {matrix_html}
        """

    elif is_coquette:
        extra_css = """
        /* 🌸 Coquette Rose & Lilac — soft, romantic, dreamy */
        .stApp {
            background-color: #fff5f8 !important;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(244,184,204,0.45), transparent 45%),
                radial-gradient(circle at 85% 85%, rgba(212,184,232,0.45), transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(255,220,235,0.3), transparent 60%),
                linear-gradient(135deg, #fff5f8 0%, #fce7f0 100%) !important;
            background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100% !important;
            background-attachment: fixed !important;
            color: #5c2e45 !important;
        }

        /* Text colors */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
        .stApp [data-testid="stMarkdownContainer"] {
            color: #5c2e45;
        }

        /* Sidebar with soft gradient */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff0f6 0%, #fce7f0 50%, #f5e8f8 100%) !important;
            border-right: 2px solid rgba(232,160,184,0.5) !important;
            box-shadow: 0 0 25px rgba(244,184,204,0.4) !important;
        }
        section[data-testid="stSidebar"] * {
            color: #5c2e45 !important;
        }

        /* Cards with pink-lilac gradient */
        div[data-testid="stExpander"], div[data-testid="stForm"] {
            background: linear-gradient(135deg, #fffafc 0%, #fdf0f5 100%) !important;
            border-radius: 16px !important;
            border: 1.5px solid rgba(232,160,184,0.5) !important;
            box-shadow: 0 4px 20px rgba(232,160,184,0.25), 0 0 30px rgba(212,184,232,0.15) !important;
        }

        /* Buttons with dreamy gradient + glow */
        .stButton>button {
            border-radius: 14px !important;
            font-weight: 700 !important;
            background: linear-gradient(135deg, #f4b8cc 0%, #e8a0b8 40%, #d4b8e8 100%) !important;
            color: #ffffff !important;
            border: none !important;
            text-shadow: 0 1px 2px rgba(92,46,69,0.3) !important;
            box-shadow: 0 0 20px rgba(244,184,204,0.55), 0 0 32px rgba(212,184,232,0.4) !important;
            transition: all 0.25s ease !important;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 0 30px rgba(244,184,204,0.8), 0 0 45px rgba(212,184,232,0.6) !important;
        }

        /* Headers in dusty rose with soft glow */
        .stApp h1, .stApp h2, .stApp h3 {
            color: #c87a94 !important;
            text-shadow: 0 0 15px rgba(244,184,204,0.6), 0 0 30px rgba(212,184,232,0.4) !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: transparent !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255,250,252,0.7) !important;
            border: 1px solid rgba(232,160,184,0.4) !important;
            border-radius: 12px 12px 0 0 !important;
            color: #5c2e45 !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #f4b8cc, #d4b8e8) !important;
            color: #ffffff !important;
            box-shadow: 0 0 18px rgba(244,184,204,0.7) !important;
        }

        /* Metrics */
        span[data-testid="stMetricValue"] {
            color: #c87a94 !important;
            text-shadow: 0 0 12px rgba(244,184,204,0.6) !important;
        }

        hr {
            border-color: rgba(232,160,184,0.3) !important;
        }

        /* Expander summary */
        div[data-testid="stExpander"] summary {
            color: #5c2e45 !important;
            text-shadow: 0 0 6px rgba(244,184,204,0.5) !important;
        }

        /* Progress bars */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #f4b8cc, #d4b8e8) !important;
        }
        """
    elif is_cyber:
        extra_css = """
        /* Cyberpunk 2099 Neon Grid and Glow */
        .stApp {
            background-color: #070814 !important;
            background-image: 
                radial-gradient(circle at 50% 0%, rgba(176,38,255,0.18), transparent 45%),
                linear-gradient(rgba(0,240,255,0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,240,255,0.05) 1px, transparent 1px) !important;
            background-size: 100% 100%, 36px 36px, 36px 36px !important;
            color: #e0f7ff !important;
        }
        div[data-testid="stExpander"], div[data-testid="stForm"], .css-1r6slb0 {
            background-color: #0c0d24 !important;
            border-radius: 14px !important;
            border: 1.5px solid #00f0ff !important;
            box-shadow: 0 0 18px rgba(0,240,255,0.3), inset 0 0 18px rgba(176,38,255,0.15) !important;
        }
        .stButton>button {
            border-radius: 12px !important;
            font-weight: 800 !important;
            background: linear-gradient(135deg, #00f0ff 0%, #b026ff 50%, #ff007f 100%) !important;
            color: #ffffff !important;
            border: none !important;
            text-shadow: 0 1px 3px rgba(0,0,0,0.8) !important;
            box-shadow: 0 0 15px rgba(0,240,255,0.45), 0 0 25px rgba(255,0,127,0.35) !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            box-shadow: 0 0 25px rgba(0,240,255,0.8), 0 0 35px rgba(255,0,127,0.6) !important;
        }
        h1, h2, h3 {
            color: #00f0ff !important;
            text-shadow: 0 0 10px rgba(0,240,255,0.4) !important;
        }
        /* Neon badges */
        span[data-testid="stMetricValue"] {
            color: #ff007f !important;
            text-shadow: 0 0 12px rgba(255,0,127,0.5) !important;
        }
        """
    else:
        extra_css = f"""
        .stApp {{
            background-color: {t['bg']};
            color: {t['text']};
        }}
        div[data-testid="stExpander"], div[data-testid="stForm"], .css-1r6slb0 {{
            background-color: {t['card']};
            border-radius: 14px;
            border: 1.5px solid {t['border']};
            box-shadow: {t['glow']};
        }}
        .stButton>button {{
            border-radius: 12px;
            font-weight: 700;
            background-color: {t['accent']};
            color: white;
            border: none;
            box-shadow: {t['glow']};
            transition: all 0.2s ease;
        }}
        .stButton>button:hover {{
            opacity: 0.92;
            transform: translateY(-1px);
        }}
        """

    if "<div class='matrix-rain-bg'" in extra_css:
        # Split CSS and HTML — Streamlit handles them better separately
        split_idx = extra_css.find("<div class='matrix-rain-bg'")
        css_part = extra_css[:split_idx]
        html_part = extra_css[split_idx:]
        st.markdown(css_part, unsafe_allow_html=True)
        st.markdown(html_part, unsafe_allow_html=True)
    else:
        css = f"""
        <style>
        {extra_css}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
# ---------------------------------------------------------
# 3. ACCURATE SOUTH AFRICAN CAPS SUBJECT & TOPIC DIRECTORY
# ---------------------------------------------------------
# Senior Phase (Gr 8-9): Mathematics, Natural Sciences, EMS, Social Sciences, Technology, English, LO
# FET Phase (Gr 10-12): Mathematics, Maths Lit, Physical Sciences, Life Sciences, Accounting, Business Studies, Economics, Geography, History, English, LO
SUBJECTS = {
    # Core GET & FET
    "mathematics": {
        "name": "Mathematics",
        "icon": "📐",
        "grades": [8, 9, 10, 11, 12],
        "topics": {
            8: ["Integers (Calculations & Signs)", "Common Fractions & Decimals", "Exponents & Powers", "Algebraic Expressions", "Geometry of Straight Lines", "Theorem of Pythagoras", "Perimeter & Area of 2D Shapes"],
            9: ["Integers & Rational Numbers", "Common Fractions & Percentages", "Theorem of Pythagoras", "Similar & Congruent Triangles", "Geometry of Straight Lines", "Factorisation & Equations", "Surface Area & Volume"],
            10: ["Quadratic Equations", "Parabola & Hyperbola Functions", "Trigonometry (Sine, Cosine, Tangent)", "Analytical Geometry", "Euclidean Geometry"],
            11: ["Quadratic Formula & Nature of Roots", "Circle Euclidean Geometry", "Trigonometric Reductions & Identities", "Analytical Geometry (Lines & Circles)"],
            12: ["Differential Calculus", "Cubic Functions & Optimization", "Circle Geometry Theorems", "Compound & Double Angle Trigonometry", "Financial Annuities"]
        }
    },
    # Senior Phase (Gr 8-9 only)
    "natural_sciences": {
        "name": "Natural Sciences (NS)",
        "icon": "🔬",
        "grades": [8, 9],
        "topics": {
            8: ["Human Digestive System", "Plant & Animal Cells", "Photosynthesis & Respiration", "Atoms & Periodic Table", "Particle Model of Matter", "Electric Circuits (Series & Parallel)"],
            9: ["Human Reproduction & Genetics", "Digestive Enzymes & Nutrition", "Forces (Gravity, Friction, Normal)", "Electric Cells & Ohm's Law", "Chemical Reactions & pH Acids/Bases", "Atmosphere & Mining in SA"]
        }
    },
    "ems": {
        "name": "Economic & Management Sciences (EMS)",
        "icon": "💰",
        "grades": [8, 9],
        "topics": {
            8: ["The Accounting Equation (A = O + L)", "Cash Receipts Journal (CRJ)", "Financial Literacy & Personal Budget", "Factors of Production", "Forms of Ownership"],
            9: ["Cash Payments Journal (CPJ)", "General Ledger & T-Accounts", "Economic Circular Flow", "Supply and Demand Equilibrium", "Business Plans & Entrepreneurship"]
        }
    },
    "social_sciences": {
        "name": "Social Sciences (SS)",
        "icon": "🌍",
        "grades": [8, 9],
        "topics": {
            8: ["Topographic Maps & 1:50 000 Scale", "Climate Regions of the World", "Settlement Patterns in South Africa", "Mineral Revolution in South Africa", "World War I Causes"],
            9: ["Contour Lines & Elevation Profiles", "Weathering & Soil Erosion", "Development Issues & Global Trade", "World War II in Europe & Pacific", "Apartheid in South Africa (1948-1994)"]
        }
    },
    "technology": {
        "name": "Technology",
        "icon": "⚙️",
        "grades": [8, 9],
        "topics": {
            8: ["Structural Analysis & Triangulation", "Class 1, 2, 3 Levers & Mechanical Advantage", "Gear Trains & Velocity Ratios", "Electrical Components & Logic"],
            9: ["Pulleys, Cams & Cranks Mechanisms", "Pneumatics & Hydraulics (Pascal's Principle)", "Electronic Circuits & Resistor Color Codes", "Preserving & Processing Materials"]
        }
    },
    # FET Phase (Gr 10-12 only)
    "physical_sciences": {
        "name": "Physical Sciences",
        "icon": "⚛️",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Motion in One Dimension (Vectors & Graphs)", "Transverse & Longitudinal Waves", "Chemical Bonding & Stoichiometry", "Electric Circuits & Ohm's Law"],
            11: ["Newton's Laws of Motion (1st, 2nd, 3rd Law)", "Intermolecular Forces", "Ideal Gases & Boyle's Law", "Stoichiometry & Quantitative Aspects"],
            12: ["Newton's Laws & Momentum / Impulse", "Work, Energy & Power", "Doppler Effect", "Organic Chemistry (IUPAC Nomenclature & Esters)", "Electrochemical Cells & Reaction Rates"]
        }
    },
    "life_sciences": {
        "name": "Life Sciences",
        "icon": "🧬",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Cell Ultra-Structure & Microscopy", "Mitosis Cell Division", "Plant Tissues & Transpiration", "Human Skeleton & Support Systems"],
            11: ["Photosynthesis (Light & Dark Phases)", "Cellular Respiration (Glycolysis & Krebs)", "Human Excretion & Nephron", "Population Ecology"],
            12: ["DNA Replication & RNA Transcription", "Genetics (Monohybrid Punnett Squares)", "Human Nervous & Endocrine Systems", "Evolution by Natural Selection"]
        }
    },
    "accounting": {
        "name": "Accounting",
        "icon": "📊",
        "grades": [10, 11, 12],
        "topics": {
            10: ["GAAP Principles & Ethics", "Financial Statements: Income Statement", "Debtors Reconciliation", "Value Added Tax (VAT)"],
            11: ["Partnership Financial Ledger", "Asset Disposal & Fixed Asset Depreciation", "Bank Reconciliation Statements", "Periodic vs Perpetual Inventory"],
            12: ["Companies: Balance Sheet & Notes", "Cash Flow Statements", "Financial Ratios & Audit Reports", "Manufacturing Cost Accounts"]
        }
    },
    "business_studies": {
        "name": "Business Studies",
        "icon": "💼",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Micro, Market & Macro Business Environments", "SWOT Analysis & Environmental Scanning", "Business Sectors (Primary, Secondary, Tertiary)", "Forms of Ownership"],
            11: ["Creative Thinking & Problem-Solving", "Stress & Crisis Management", "Team Dynamics & Conflict Management", "Marketing Function & 4Ps"],
            12: ["Macro Environment Strategies (Porter's Five Forces)", "Human Resource Function", "Ethics, Professionalism & Corporate Social Responsibility", "Quality of Performance"]
        }
    },
    "economics": {
        "name": "Economics",
        "icon": "📈",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Basic Economic Problem (Scarcity)", "Circular Flow of Goods & Services", "Markets (Perfect & Imperfect)", "South African Public Sector"],
            11: ["Factors of Production & Remuneration", "Economic Growth vs Economic Development", "Poverty & Wealth Inequality (Gini Coefficient)", "Globalisation & Trade"],
            12: ["Macroeconomics: Circular Flow & National Income", "Business Cycles & Forecasting", "Public Sector Intervention", "Foreign Exchange Markets & Balance of Payments"]
        }
    },
    "geography": {
        "name": "Geography",
        "icon": "🗺️",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Synoptic Weather Charts & Isobars", "Plate Tectonics & Continental Drift", "Population Structure & Pyramids", "Water Resources in South Africa"],
            11: ["Global Air Circulation & Cells (Hadley, Ferrel, Polar)", "Geomorphology: Horizontal & Inclined Strata", "Development Geography in Africa", "Soil Erosion & Desertification"],
            12: ["Mid-Latitude Cyclones & Tropical Cyclones", "Subtropical Anticyclones & Berg Winds", "Drainage Basins & Fluvial Landforms", "Rural-Urban Migration & Settlements"]
        }
    },
    "history": {
        "name": "History",
        "icon": "🏛️",
        "grades": [10, 11, 12],
        "topics": {
            10: ["The World in 1600 (Songhai & Ming Dynasty)", "French Revolution & Human Rights", "Transformation in Southern Africa (Shaka & Zulu)", "Colonial Expansion"],
            11: ["Communism in Russia (1900-1940)", "Capitalism in USA & Great Depression", "Ideas of Race in the Late 19th & 20th Centuries", "Nationalisms in South Africa"],
            12: ["Cold War & Superpower Rivalries", "Independence in Africa (Congo & Tanzania)", "Civil Rights Movement & Black Power in USA", "Resistance in South Africa & End of Apartheid"]
        }
    },
    "maths_lit": {
        "name": "Mathematical Literacy",
        "icon": "🧮",
        "grades": [10, 11, 12],
        "topics": {
            10: ["Municipal Tariffs (Water & Electricity)", "Personal Budgeting & Expense Statements", "Measurement: Perimeter & Area Conversions", "Data Handling: Mean, Median, Mode"],
            11: ["Personal Income Tax & Rebates", "Hire Purchase Loans & Simple vs Compound Interest", "Packaging & Box Stacking in Cargo", "Architectural Floor Plans & Scales"],
            12: ["SARS Income Tax Brackets & Medical Tax Credits", "Break-Even Point Graphs", "Inflation & Purchasing Power", "Exchange Rates & Currency Conversions"]
        }
    },
    "english": {
        "name": "English (HL & FAL)",
        "icon": "📖",
        "grades": [8, 9, 10, 11, 12],
        "topics": {
            8: ["Figures of Speech (Metaphor, Simile, Personification)", "Active and Passive Voice", "Direct and Indirect Speech", "Parts of Speech & Punctuation"],
            9: ["Sentence Structures & Clauses", "Critical Language Awareness & Bias", "Visual Literacy & Cartoon Analysis", "Poetry Terminology & Rhyme Schemes"],
            10: ["Parts of Speech & Concord Agreement", "Advertising Techniques & Emotive Language", "Summary Writing (7 Concise Points)", "Idiomatic Expressions"],
            11: ["Ambiguity, Irony & Satire", "Cartoons & Visual Irony Analysis", "Reported Speech & Subjunctive Mood", "Formal Register & Style"],
            12: ["Formal Register & Error Identification", "Rhetorical Devices & Textual Cohesion", "Complex Poetry & Literary Motifs", "Advanced Visual Literacy"]
        }
    },
    "life_orientation": {
        "name": "Life Orientation (LO)",
        "icon": "🧭",
        "grades": [8, 9, 10, 11, 12],
        "topics": {
            8: ["Development of the Self & Self-Concept", "Healthy Lifestyle & Substance Abuse", "Human Rights & Social Justice in SA", "Career Choices & Subjects"],
            9: ["Goal Setting (SMART Principles)", "Constitutional Rights & Nation-Building", "Study Skills & Exam Preparation Techniques", "Career Path Planning"],
            10: ["Self-Awareness & Self-Esteem", "Study Methods & Critical Thinking", "Life Roles & Relationships", "Environmental Health & Sustainability"],
            11: ["Stress Management & Coping Mechanisms", "Democratic Participation & Governance", "Career & Study Qualifications Framework (NQF)", "Physical Fitness & Wellness Wheel"],
            12: ["Development of the Self in Society", "Study Skills & Transition to Higher Education", "Labor Market & Human Resources", "Democracy & Human Rights Violations"]
        }
    }
}

# ---------------------------------------------------------
# 4. COMPREHENSIVE SVG DIAGRAM ENGINE (ALL SUBJECTS)
# ---------------------------------------------------------
# ---------------------------------------------------------
# 3B. DIAGRAM QUIZ SPOT DATA
# Coordinates are relative to each SVG's viewBox
# ---------------------------------------------------------
DIAGRAM_QUIZ_SPOTS = {
    "human_digestive": [
        {"id": 1, "x": 199, "y": 165, "label": "Stomach", "alt": ["stomach"]},
        {"id": 2, "x": 155, "y": 145, "label": "Liver", "alt": ["liver"]},
        {"id": 3, "x": 195, "y": 250, "label": "Small Intestine", "alt": ["small intestine", "ileum"]},
        {"id": 4, "x": 200, "y": 220, "label": "Large Intestine", "alt": ["large intestine", "colon"]},
        {"id": 5, "x": 178, "y": 100, "label": "Esophagus", "alt": ["esophagus", "oesophagus"]},
    ],
    "human_heart": [
        {"id": 1, "x": 172, "y": 150, "label": "Right Atrium", "alt": ["right atrium", "ra"]},
        {"id": 2, "x": 250, "y": 150, "label": "Left Atrium", "alt": ["left atrium", "la"]},
        {"id": 3, "x": 172, "y": 225, "label": "Right Ventricle", "alt": ["right ventricle", "rv"]},
        {"id": 4, "x": 250, "y": 225, "label": "Left Ventricle", "alt": ["left ventricle", "lv"]},
    ],
    "plant_cell": [
        {"id": 1, "x": 110, "y": 115, "label": "Nucleus", "alt": ["nucleus"]},
        {"id": 2, "x": 230, "y": 165, "label": "Vacuole", "alt": ["vacuole", "central vacuole"]},
        {"id": 3, "x": 110, "y": 215, "label": "Chloroplast", "alt": ["chloroplast"]},
        {"id": 4, "x": 335, "y": 210, "label": "Mitochondrion", "alt": ["mitochondrion", "mitochondria"]},
    ],
    "electric_circuit": [
        {"id": 1, "x": 222, "y": 65, "label": "Battery", "alt": ["battery", "cell"]},
        {"id": 2, "x": 70, "y": 120, "label": "Ammeter", "alt": ["ammeter"]},
        {"id": 3, "x": 220, "y": 185, "label": "Resistor", "alt": ["resistor"]},
        {"id": 4, "x": 220, "y": 220, "label": "Voltmeter", "alt": ["voltmeter"]},
    ],
    "atom_model": [
        {"id": 1, "x": 120, "y": 90, "label": "Nucleus", "alt": ["nucleus"]},
        {"id": 2, "x": 50, "y": 90, "label": "Electron (outer shell)", "alt": ["electron", "outer electron", "valence electron"]},
    ],
    "biology_punnett": [
        {"id": 1, "x": 130, "y": 60, "label": "BB", "alt": ["bb", "homozygous dominant"]},
        {"id": 2, "x": 190, "y": 100, "label": "bb", "alt": ["bb", "homozygous recessive"]},
    ],
    "lever_diagram": [
        {"id": 1, "x": 140, "y": 80, "label": "Fulcrum", "alt": ["fulcrum", "pivot"]},
        {"id": 2, "x": 50, "y": 40, "label": "Effort", "alt": ["effort", "effort force"]},
        {"id": 3, "x": 232, "y": 48, "label": "Load", "alt": ["load"]},
    ],
    "pythagoras": [
        {"id": 1, "x": 125, "y": 130, "label": "Hypotenuse", "alt": ["hypotenuse", "hyp", "c"]},
    ],
    "contour_map": [
        {"id": 1, "x": 130, "y": 80, "label": "Peak", "alt": ["peak", "summit", "top"]},
    ],
    "accounting_scale": [
        {"id": 1, "x": 50, "y": 90, "label": "Assets", "alt": ["assets", "a"]},
        {"id": 2, "x": 270, "y": 90, "label": "Owners Equity + Liabilities", "alt": ["owners equity", "equity", "oe", "liabilities"]},
    ],
    "supply_demand": [
        {"id": 1, "x": 130, "y": 80, "label": "Equilibrium", "alt": ["equilibrium", "market equilibrium", "e"]},
    ],
    "physics_free_body": [
        {"id": 1, "x": 130, "y": 90, "label": "Mass", "alt": ["mass", "block"]},
        {"id": 2, "x": 195, "y": 85, "label": "Applied force", "alt": ["applied force", "f_app", "force"]},
        {"id": 3, "x": 60, "y": 85, "label": "Friction", "alt": ["friction", "f_k", "kinetic friction"]},
    ],
    "cartesian_parabola": [
        {"id": 1, "x": 260, "y": 170, "label": "Turning Point", "alt": ["turning point", "vertex", "turning point (p,q)"]},
        {"id": 2, "x": 160, "y": 120, "label": "Y-intercept", "alt": ["y-intercept", "y intercept", "y-int"]},
        {"id": 3, "x": 260, "y": 90, "label": "Axis of Symmetry", "alt": ["axis of symmetry", "line of symmetry"]},
    ],
}
def render_diagram_svg(diagram_type, data):
    """Generate crisp, responsive, high-contrast SVG diagrams for every CAPS subject."""
    if diagram_type == "pythagoras":
        a = data.get("a", 3)
        b = data.get("b", 4)
        c = data.get("c", 5)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 260 160" width="280" height="160" style="background: rgba(99,102,241,0.08); border-radius: 12px; border: 1px dashed #6366f1;">
                <polygon points="40,130 210,130 40,30" fill="rgba(99, 102, 241, 0.25)" stroke="#6366f1" stroke-width="2.5" />
                <polyline points="40,115 55,115 55,130" fill="none" stroke="#6366f1" stroke-width="2" />
                <text x="25" y="85" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="end">a = {a}</text>
                <text x="125" y="148" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">b = {b}</text>
                <text x="140" y="70" fill="#f43f5e" font-size="13" font-weight="bold">c (hyp) = {c}</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Theorem of Pythagoras ($c^2 = a^2 + b^2$)</p>
        </div>
        """

    elif diagram_type == "geometry_lines":
        angle_a = data.get("angleA", "110°")
        angle_x = data.get("angleX", "x")
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 280 140" width="290" height="140" style="background: rgba(6,182,212,0.08); border-radius: 12px; border: 1px dashed #06b6d4;">
                <line x1="20" y1="40" x2="260" y2="40" stroke="#06b6d4" stroke-width="2.5" />
                <line x1="20" y1="100" x2="260" y2="100" stroke="#06b6d4" stroke-width="2.5" />
                <line x1="55" y1="15" x2="225" y2="125" stroke="#f43f5e" stroke-width="2.5" />
                <text x="110" y="60" fill="#eab308" font-size="12" font-weight="bold">{angle_a}</text>
                <text x="175" y="120" fill="#10b981" font-size="13" font-weight="bold">{angle_x}</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Parallel Lines with Transversal Line</p>
        </div>
        """

    elif diagram_type == "number_line":
        start = data.get("start", -5)
        jump = data.get("jump", 8)
        end = data.get("end", start + jump)
        min_v = min(start, end, -6) - 1
        max_v = max(start, end, 6) + 1
        span = max(1, max_v - min_v)

        def get_pos(val):
            return 30 + ((val - min_v) / span) * 310

        x_s = get_pos(start)
        x_e = get_pos(end)
        mid_x = (x_s + x_e) / 2
        is_fwd = end >= start

        ticks = []
        for t in range(min_v, max_v + 1):
            tx = get_pos(t)
            is_zero = (t == 0)
            col = "#38bdf8" if is_zero else ("#f43f5e" if (t == start or t == end) else "#64748b")
            sw = "2.5" if is_zero else "1.5"
            ticks.append(f'<line x1="{tx}" y1="58" x2="{tx}" y2="72" stroke="{col}" stroke-width="{sw}" />')
            ticks.append(f'<text x="{tx}" y="87" fill="{col}" font-size="9" font-family="monospace" text-anchor="middle">{t}</text>')
        ticks_str = "".join(ticks)

        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 370 105" width="350" height="105" style="background: rgba(15,23,42,0.6); border-radius: 12px; border: 1px dashed #6366f1;">
                <line x1="20" y1="65" x2="350" y2="65" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
                <polygon points="14,65 22,61 22,69" fill="#94a3b8" />
                <polygon points="356,65 348,61 348,69" fill="#94a3b8" />
                {ticks_str}
                <path d="M {x_s} 54 Q {mid_x} 18 {x_e} 54" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="4,4" />
                <circle cx="{x_s}" cy="65" r="4.5" fill="#f43f5e" />
                <circle cx="{x_e}" cy="65" r="5" fill="#10b981" />
                <text x="{mid_x}" y="18" fill="#f59e0b" font-size="11" font-weight="bold" text-anchor="middle">Jump ({'+' if is_fwd else ''}{jump})</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Number Line Integer Addition ({start} {'+' if is_fwd else ''}{jump} = {end})</p>
        </div>
        """

    elif diagram_type == "fraction_model":
        num = data.get("num", 3)
        den = max(1, data.get("den", 4))
        boxes = []
        bw = 250 / den
        for i in range(den):
            shaded = i < num
            fill_c = "rgba(245, 158, 11, 0.45)" if shaded else "rgba(255, 255, 255, 0.05)"
            stroke_c = "#f59e0b" if shaded else "#475569"
            bx = 25 + i * bw
            boxes.append(f'<rect x="{bx}" y="32" width="{bw}" height="42" fill="{fill_c}" stroke="{stroke_c}" stroke-width="2" />')
            if shaded:
                boxes.append(f'<text x="{bx + bw/2}" y="57" fill="#fef08a" font-size="11" font-weight="bold" text-anchor="middle">1/{den}</text>')
        boxes_str = "".join(boxes)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 300 100" width="310" height="100" style="background: rgba(15,23,42,0.6); border-radius: 12px; border: 1px dashed #f59e0b;">
                {boxes_str}
                <text x="150" y="22" fill="#fbbf24" font-size="11" font-weight="bold" text-anchor="middle">Fraction Strip: {num}/{den} ({num} of {den} parts)</text>
                <text x="150" y="90" fill="#94a3b8" font-size="9" text-anchor="middle">Written horizontal fraction model</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Fraction Area Model</p>
        </div>
        """
    elif diagram_type in ["human_digestive", "digestive_system"]:
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 460 350" width="100%" style="max-width: 480px; height: auto; background: rgba(16,185,129,0.05); border-radius: 16px; border: 1.5px solid rgba(16,185,129,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <defs>
                    <linearGradient id="stomachGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#fb7185" />
                        <stop offset="100%" stop-color="#e11d48" />
                    </linearGradient>
                    <linearGradient id="liverGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#d97706" />
                        <stop offset="100%" stop-color="#92400e" />
                    </linearGradient>
                    <linearGradient id="smallIntGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#fbcfe8" />
                        <stop offset="100%" stop-color="#f472b6" />
                    </linearGradient>
                </defs>
                <text x="230" y="24" fill="#34d399" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">HUMAN ALIMENTARY CANAL & DIGESTIVE SYSTEM</text>
                
                <!-- Body Silhouette -->
                <path d="M 170 35 C 190 35 200 48 200 62 C 200 70 195 78 190 85 L 195 98 L 265 105 C 285 110 290 140 290 180 L 290 320 C 290 335 275 340 260 340 L 160 340 C 145 340 130 335 130 320 L 130 180 C 130 140 135 110 155 105 L 168 98 L 165 85 C 160 78 150 70 150 55 C 150 40 160 35 170 35 Z" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.12)" stroke-width="1.5" />
                
                <!-- Oral Cavity & Salivary Glands -->
                <ellipse cx="178" cy="58" rx="8" ry="5" fill="#f43f5e" opacity="0.8" />
                <circle cx="168" cy="62" r="5" fill="#facc15" stroke="#eab308" stroke-width="1" />
                <circle cx="188" cy="65" r="4" fill="#facc15" stroke="#eab308" stroke-width="1" />
                <text x="75" y="58" fill="#facc15" font-size="10" font-weight="bold">Salivary Glands (Amylase)</text>
                <line x1="135" y1="58" x2="165" y2="60" stroke="#facc15" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Esophagus -->
                <path d="M 180 65 L 180 135" fill="none" stroke="#f472b6" stroke-width="5" stroke-linecap="round" />
                <text x="75" y="105" fill="#f472b6" font-size="10" font-weight="bold">Esophagus (Peristalsis)</text>
                <line x1="135" y1="105" x2="176" y2="105" stroke="#f472b6" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Liver -->
                <path d="M 152 130 C 172 125 185 135 182 165 C 175 175 145 170 140 155 C 138 142 142 132 152 130 Z" fill="url(#liverGrad)" stroke="#b45309" stroke-width="1.5" />
                <circle cx="168" cy="158" r="4" fill="#22c55e" stroke="#15803d" stroke-width="1" />
                <text x="70" y="145" fill="#f59e0b" font-size="10" font-weight="bold">Liver (Bile Production)</text>
                <line x1="132" y1="145" x2="148" y2="145" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2,2" />
                <text x="70" y="165" fill="#4ade80" font-size="9" font-weight="bold">Gallbladder (Stores Bile)</text>
                <line x1="132" y1="163" x2="164" y2="158" stroke="#4ade80" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Stomach (J-shaped) -->
                <path d="M 180 135 C 195 135 228 145 225 175 C 220 195 190 195 180 185 C 175 175 175 155 180 135 Z" fill="url(#stomachGrad)" stroke="#be123c" stroke-width="1.5" />
                <text x="365" y="150" fill="#f43f5e" font-size="10" font-weight="bold" text-anchor="middle">Stomach</text>
                <text x="365" y="164" fill="#fda4af" font-size="8.5" text-anchor="middle">HCl (pH 2) + Pepsin</text>
                <line x1="220" y1="160" x2="310" y2="160" stroke="#f43f5e" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Pancreas -->
                <ellipse cx="195" cy="188" rx="16" ry="5" fill="#facc15" stroke="#ca8a04" stroke-width="1" transform="rotate(-10 195 188)" />
                <text x="365" y="192" fill="#facc15" font-size="10" font-weight="bold" text-anchor="middle">Pancreas (Lipase/Insulin)</text>
                <line x1="210" y1="188" x2="295" y2="188" stroke="#facc15" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Large Intestine (Colon) -->
                <path d="M 160 270 L 160 205 C 160 195 170 195 180 195 L 230 195 C 240 195 245 200 245 210 L 245 270 L 235 270 L 235 210 L 175 210 L 175 270 Z" fill="none" stroke="#a1a1aa" stroke-width="10" stroke-linejoin="round" stroke-linecap="round" />
                <text x="365" y="225" fill="#e4e4e7" font-size="10" font-weight="bold" text-anchor="middle">Large Intestine (Colon)</text>
                <text x="365" y="238" fill="#a1a1aa" font-size="8.5" text-anchor="middle">Water & Mineral Reabsorption</text>
                <line x1="245" y1="225" x2="295" y2="225" stroke="#e4e4e7" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Small Intestine (Coiled Villi) -->
                <path d="M 180 215 Q 200 220 220 215 Q 230 230 210 235 Q 185 235 175 245 Q 190 260 215 255 Q 225 265 200 270 Q 180 270 178 260" fill="none" stroke="url(#smallIntGrad)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
                <text x="70" y="240" fill="#f472b6" font-size="10" font-weight="bold">Small Intestine (Ileum)</text>
                <text x="70" y="254" fill="#fbcfe8" font-size="8.5">Villi Nutrient Absorption</text>
                <line x1="130" y1="240" x2="175" y2="240" stroke="#f472b6" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Rectum & Anus -->
                <rect x="195" y="275" width="8" height="24" rx="3" fill="#71717a" stroke="#52525b" stroke-width="1" />
                <circle cx="199" cy="303" r="4" fill="#e11d48" />
                <text x="365" y="285" fill="#f43f5e" font-size="10" font-weight="bold" text-anchor="middle">Rectum & Anus (Egestion)</text>
                <line x1="205" y1="290" x2="295" y2="290" stroke="#f43f5e" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Ingestion to Egestion Legend Bar -->
                <rect x="50" y="322" width="360" height="20" rx="6" fill="rgba(0,0,0,0.4)" stroke="rgba(255,255,255,0.1)" />
                <text x="230" y="336" fill="#94a3b8" font-size="9" font-weight="bold" text-anchor="middle">Ingestion (Mouth) → Digestion (Stomach) → Absorption (Villi) → Egestion (Anus)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Authentic Human Alimentary Canal Anatomy (CAPS Life & Natural Sciences)</p>
        </div>
        """

    elif diagram_type == "human_heart":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 330" width="100%" style="max-width: 480px; height: auto; background: rgba(244,63,94,0.05); border-radius: 16px; border: 1.5px solid rgba(244,63,94,0.35); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <defs>
                    <linearGradient id="deoxGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#38bdf8" />
                        <stop offset="100%" stop-color="#1d4ed8" />
                    </linearGradient>
                    <linearGradient id="oxGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#f43f5e" />
                        <stop offset="100%" stop-color="#9f1239" />
                    </linearGradient>
                </defs>
                <text x="220" y="24" fill="#fb7185" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">MAMMALIAN DOUBLE-CIRCULATORY HEART ANATOMY</text>
                
                <!-- Superior Vena Cava -->
                <rect x="140" y="45" width="22" height="48" rx="5" fill="url(#deoxGrad)" />
                <!-- Aortic Arch -->
                <path d="M 215 95 C 215 40 270 40 270 85 L 285 85 C 285 25 195 25 195 95 Z" fill="url(#oxGrad)" />
                <rect x="220" y="28" width="10" height="18" fill="#e11d48" />
                <rect x="238" y="24" width="10" height="22" fill="#e11d48" />
                <rect x="256" y="28" width="10" height="18" fill="#e11d48" />
                
                <!-- Pulmonary Artery -->
                <path d="M 200 90 L 160 80 L 160 95 L 195 105 Z" fill="#0284c7" />
                <path d="M 220 90 L 270 82 L 270 96 L 225 104 Z" fill="#0284c7" />

                <!-- Main Heart Muscular Mass -->
                <!-- Right Side (Deoxygenated / Blue) -->
                <path d="M 210 110 C 150 110 135 150 135 195 C 135 240 180 275 210 295 L 210 110 Z" fill="url(#deoxGrad)" stroke="#1e40af" stroke-width="2" />
                <!-- Left Side (Oxygenated / Red - Thicker Myocardium) -->
                <path d="M 210 110 L 210 295 C 240 275 290 240 290 195 C 290 145 270 110 210 110 Z" fill="url(#oxGrad)" stroke="#881337" stroke-width="3" />
                
                <!-- Septum Divider Line -->
                <line x1="210" y1="110" x2="210" y2="295" stroke="#f8fafc" stroke-width="3.5" stroke-dasharray="4,3" />

                <!-- Internal Chamber Labels -->
                <text x="172" y="150" fill="#ffffff" font-size="12" font-weight="bold" text-anchor="middle">RA</text>
                <text x="172" y="164" fill="#bae6fd" font-size="8" text-anchor="middle">Right Atrium</text>
                <text x="172" y="225" fill="#ffffff" font-size="12" font-weight="bold" text-anchor="middle">RV</text>
                <text x="172" y="239" fill="#bae6fd" font-size="8" text-anchor="middle">Right Ventricle</text>

                <text x="250" y="150" fill="#ffffff" font-size="12" font-weight="bold" text-anchor="middle">LA</text>
                <text x="250" y="164" fill="#fecdd3" font-size="8" text-anchor="middle">Left Atrium</text>
                <text x="250" y="225" fill="#ffffff" font-size="12" font-weight="bold" text-anchor="middle">LV</text>
                <text x="250" y="239" fill="#fecdd3" font-size="8" text-anchor="middle">Thick Myocardium</text>

                <!-- Flow Direction Arrows -->
                <path d="M 151 70 L 151 125" fill="none" stroke="#67e8f9" stroke-width="2.5" marker-end="url(#arrow)" />
                <path d="M 172 175 L 172 205" fill="none" stroke="#67e8f9" stroke-width="2.5" />
                <path d="M 250 175 L 250 205" fill="none" stroke="#fecdd3" stroke-width="2.5" />

                <!-- Callout Labels -->
                <text x="65" y="70" fill="#38bdf8" font-size="9.5" font-weight="bold">Superior Vena Cava (Inflow)</text>
                <line x1="120" y1="70" x2="138" y2="70" stroke="#38bdf8" stroke-width="1" stroke-dasharray="2,2" />

                <text x="360" y="55" fill="#f43f5e" font-size="9.5" font-weight="bold" text-anchor="middle">Systemic Aorta (High Pressure)</text>
                <line x1="280" y1="55" x2="260" y2="55" stroke="#f43f5e" stroke-width="1" stroke-dasharray="2,2" />

                <text x="65" y="195" fill="#38bdf8" font-size="9.5" font-weight="bold">Tricuspid Valve</text>
                <line x1="125" y1="195" x2="165" y2="188" stroke="#38bdf8" stroke-width="1" stroke-dasharray="2,2" />

                <text x="365" y="195" fill="#f43f5e" font-size="9.5" font-weight="bold" text-anchor="middle">Bicuspid (Mitral) Valve</text>
                <line x1="260" y1="188" x2="305" y2="195" stroke="#f43f5e" stroke-width="1" stroke-dasharray="2,2" />

                <!-- Bottom Legend -->
                <rect x="50" y="306" width="340" height="18" rx="5" fill="rgba(0,0,0,0.4)" stroke="rgba(255,255,255,0.1)" />
                <text x="135" y="318" fill="#38bdf8" font-size="9" font-weight="bold">■ Blue = Deoxygenated Blood (To Lungs)</text>
                <text x="290" y="318" fill="#f43f5e" font-size="9" font-weight="bold">■ Red = Oxygenated Blood (To Body)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Authentic Mammalian 4-Chamber Heart Flow (CAPS Life Sciences)</p>
        </div>
        """

    elif diagram_type == "plant_cell":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 310" width="100%" style="max-width: 480px; height: auto; background: rgba(34,197,94,0.05); border-radius: 16px; border: 1.5px solid rgba(34,197,94,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="24" fill="#4ade80" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">ULTRASTRUCTURE OF A TYPICAL PLANT CELL</text>
                
                <!-- Cellulose Cell Wall (outer rigid polygon) -->
                <polygon points="50,60 130,40 310,40 390,60 410,230 360,280 110,280 40,240" fill="rgba(22,101,52,0.3)" stroke="#15803d" stroke-width="7" stroke-linejoin="round" />
                <!-- Plasma Membrane (inner boundary) -->
                <polygon points="54,64 131,45 307,45 385,64 404,227 356,275 113,275 45,236" fill="rgba(34,197,94,0.15)" stroke="#4ade80" stroke-width="2" stroke-linejoin="round" />

                <!-- Large Central Vacuole (Turgor Pressure) -->
                <ellipse cx="230" cy="165" rx="95" ry="60" fill="rgba(56,189,248,0.25)" stroke="#38bdf8" stroke-width="2" />
                <text x="230" y="160" fill="#bae6fd" font-size="11" font-weight="bold" text-anchor="middle">Large Central Vacuole</text>
                <text x="230" y="174" fill="#e0f2fe" font-size="8.5" text-anchor="middle">(Cell Sap & Turgor Pressure)</text>

                <!-- Nucleus, Nucleolus, and Chromatin -->
                <circle cx="110" cy="115" r="28" fill="rgba(168,85,247,0.35)" stroke="#a855f7" stroke-width="2" />
                <circle cx="110" cy="115" r="10" fill="#7e22ce" stroke="#c084fc" stroke-width="1.5" />
                <text x="110" y="155" fill="#d8b4fe" font-size="9" font-weight="bold" text-anchor="middle">Nucleus & DNA</text>

                <!-- Chloroplasts with Thylakoid Stacks (Grana) -->
                <g transform="translate(110, 215)">
                    <ellipse cx="0" cy="0" rx="20" ry="12" fill="#16a34a" stroke="#22c55e" stroke-width="1.5" transform="rotate(-15)" />
                    <line x1="-10" y1="-3" x2="10" y2="-3" stroke="#bbf7d0" stroke-width="1.5" />
                    <line x1="-10" y1="2" x2="10" y2="2" stroke="#bbf7d0" stroke-width="1.5" />
                    <text x="0" y="24" fill="#86efac" font-size="8.5" font-weight="bold" text-anchor="middle">Chloroplast (Grana)</text>
                </g>
                <g transform="translate(340, 95)">
                    <ellipse cx="0" cy="0" rx="18" ry="11" fill="#16a34a" stroke="#22c55e" stroke-width="1.5" transform="rotate(25)" />
                    <line x1="-8" y1="-2" x2="8" y2="-2" stroke="#bbf7d0" stroke-width="1.5" />
                    <line x1="-8" y1="3" x2="8" y2="3" stroke="#bbf7d0" stroke-width="1.5" />
                </g>

                <!-- Mitochondria (Cristae) -->
                <g transform="translate(335, 210)">
                    <ellipse cx="0" cy="0" rx="19" ry="11" fill="#f97316" stroke="#ea580c" stroke-width="1.5" transform="rotate(-20)" />
                    <path d="M -12 0 Q -6 -5 0 0 Q 6 5 12 0" fill="none" stroke="#ffedd5" stroke-width="1.5" />
                    <text x="0" y="24" fill="#fdba74" font-size="8.5" font-weight="bold" text-anchor="middle">Mitochondrion (ATP)</text>
                </g>

                <!-- Labels -->
                <text x="350" y="40" fill="#86efac" font-size="10" font-weight="bold">Cellulose Cell Wall</text>
                <line x1="330" y1="42" x2="280" y2="42" stroke="#86efac" stroke-width="1" stroke-dasharray="2,2" />
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Plant Cell Microscopic Anatomy (CAPS Life Sciences Grade 10-12)</p>
        </div>
        """

    elif diagram_type == "electric_circuit":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 240" width="100%" style="max-width: 480px; height: auto; background: rgba(59,130,246,0.05); border-radius: 16px; border: 1.5px solid rgba(59,130,246,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="24" fill="#60a5fa" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">STANDARD DIRECT CURRENT (DC) CIRCUIT DIAGRAM</text>
                
                <!-- Circuit Loop Wire -->
                <rect x="70" y="55" width="300" height="130" fill="none" stroke="#94a3b8" stroke-width="3" rx="10" />

                <!-- Battery (DC Voltage Source) at Top -->
                <rect x="185" y="48" width="70" height="16" fill="#0c1022" />
                <line x1="205" y1="42" x2="205" y2="70" stroke="#f43f5e" stroke-width="3.5" />
                <line x1="217" y1="48" x2="217" y2="64" stroke="#38bdf8" stroke-width="5" />
                <line x1="227" y1="42" x2="227" y2="70" stroke="#f43f5e" stroke-width="3.5" />
                <line x1="239" y1="48" x2="239" y2="64" stroke="#38bdf8" stroke-width="5" />
                <text x="195" y="40" fill="#f43f5e" font-size="11" font-weight="bold">+</text>
                <text x="247" y="40" fill="#38bdf8" font-size="11" font-weight="bold">-</text>
                <text x="222" y="86" fill="#fbbf24" font-size="10" font-weight="bold" text-anchor="middle">Battery (V = 12V)</text>

                <!-- Switch (Closed) on Right -->
                <rect x="360" y="105" width="20" height="30" fill="#0c1022" />
                <circle cx="370" cy="110" r="3.5" fill="#facc15" />
                <circle cx="370" cy="130" r="3.5" fill="#facc15" />
                <line x1="370" y1="110" x2="370" y2="130" stroke="#22c55e" stroke-width="3" />
                <text x="395" y="123" fill="#4ade80" font-size="9" font-weight="bold">Closed Switch (S)</text>

                <!-- Ammeter (A in Series) on Left -->
                <rect x="58" y="105" width="24" height="30" fill="#0c1022" />
                <circle cx="70" cy="120" r="14" fill="#1e293b" stroke="#38bdf8" stroke-width="2" />
                <text x="70" y="125" fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">A</text>
                <text x="45" y="123" fill="#38bdf8" font-size="9" font-weight="bold" text-anchor="end">Ammeter (I)</text>

                <!-- Resistor (Zig-Zag) at Bottom -->
                <rect x="175" y="175" width="90" height="20" fill="#0c1022" />
                <path d="M 175 185 L 185 175 L 195 195 L 205 175 L 215 195 L 225 175 L 235 195 L 245 175 L 255 185 H 265" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linejoin="round" />
                <text x="220" y="206" fill="#f59e0b" font-size="10" font-weight="bold" text-anchor="middle">Resistor R = 6 Ω</text>

                <!-- Voltmeter in Parallel across Resistor -->
                <path d="M 165 185 L 165 220 L 275 220 L 275 185" fill="none" stroke="#a855f7" stroke-width="1.5" stroke-dasharray="3,3" />
                <circle cx="220" cy="220" r="12" fill="#1e293b" stroke="#a855f7" stroke-width="2" />
                <text x="220" y="224" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">V</text>
                <text x="290" y="224" fill="#c084fc" font-size="9" font-weight="bold">Voltmeter in Parallel</text>

                <!-- Conventional Current Arrow -->
                <line x1="140" y1="55" x2="110" y2="55" stroke="#f43f5e" stroke-width="2" />
                <polygon points="105,55 115,51 115,59" fill="#f43f5e" />
                <text x="125" y="47" fill="#f43f5e" font-size="8.5" font-weight="bold">Current (I)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Ohm's Law Circuit ($V = I \cdot R$) with Series Ammeter & Parallel Voltmeter</p>
        </div>
        """

    elif diagram_type == "optics_lens":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 220" width="100%" style="max-width: 480px; height: auto; background: rgba(99,102,241,0.05); border-radius: 16px; border: 1.5px solid rgba(99,102,241,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="22" fill="#818cf8" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">BICONVEX LENS RAY DIAGRAM & REFRACTION</text>
                
                <!-- Principal Axis -->
                <line x1="20" y1="110" x2="420" y2="110" stroke="#64748b" stroke-width="2" />
                <text x="415" y="125" fill="#94a3b8" font-size="9" text-anchor="end">Principal Axis</text>

                <!-- Biconvex Lens (Center) -->
                <ellipse cx="220" cy="110" rx="14" ry="80" fill="rgba(56,189,248,0.25)" stroke="#38bdf8" stroke-width="2.5" />
                <line x1="220" y1="20" x2="220" y2="200" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="3,3" />
                <text x="220" y="200" fill="#38bdf8" font-size="9" font-weight="bold" text-anchor="middle">Optical Centre (O)</text>

                <!-- Focal Points -->
                <circle cx="140" cy="110" r="3.5" fill="#facc15" />
                <text x="140" y="126" fill="#facc15" font-size="10" font-weight="bold" text-anchor="middle">F₁</text>
                <circle cx="60" cy="110" r="3.5" fill="#facc15" />
                <text x="60" y="126" fill="#facc15" font-size="10" font-weight="bold" text-anchor="middle">2F₁</text>

                <circle cx="300" cy="110" r="3.5" fill="#facc15" />
                <text x="300" y="126" fill="#facc15" font-size="10" font-weight="bold" text-anchor="middle">F₂</text>
                <circle cx="380" cy="110" r="3.5" fill="#facc15" />
                <text x="380" y="126" fill="#facc15" font-size="10" font-weight="bold" text-anchor="middle">2F₂</text>

                <!-- Object Arrow (Beyond 2F) -->
                <line x1="80" y1="110" x2="80" y2="50" stroke="#10b981" stroke-width="3" />
                <polygon points="80,44 74,54 86,54" fill="#10b981" />
                <text x="80" y="38" fill="#34d399" font-size="10" font-weight="bold" text-anchor="middle">Object</text>

                <!-- Ray 1: Parallel to axis, refracts through F2 -->
                <line x1="80" y1="50" x2="220" y2="50" stroke="#f43f5e" stroke-width="2" />
                <line x1="220" y1="50" x2="360" y2="155" stroke="#f43f5e" stroke-width="2" />

                <!-- Ray 2: Passes straight through Optical Centre O -->
                <line x1="80" y1="50" x2="360" y2="155" stroke="#3b82f6" stroke-width="2" />

                <!-- Inverted Real Image Formed between F2 and 2F2 -->
                <line x1="360" y1="110" x2="360" y2="155" stroke="#f59e0b" stroke-width="3" />
                <polygon points="360,161 354,151 366,151" fill="#f59e0b" />
                <text x="360" y="176" fill="#fbbf24" font-size="10" font-weight="bold" text-anchor="middle">Real Inverted Image</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Geometric Ray Optics for Convex Lenses (Real, Inverted & Diminished Image)</p>
        </div>
        """

    elif diagram_type == "cartesian_parabola":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 260" width="100%" style="max-width: 480px; height: auto; background: rgba(168,85,247,0.05); border-radius: 16px; border: 1.5px solid rgba(168,85,247,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="24" fill="#c084fc" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">QUADRATIC FUNCTION PARABOLA: y = a(x - p)² + q</text>
                
                <!-- Grid Lines -->
                <line x1="40" y1="80" x2="400" y2="80" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
                <line x1="40" y1="140" x2="400" y2="140" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
                <line x1="40" y1="200" x2="400" y2="200" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
                <line x1="100" y1="40" x2="100" y2="230" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
                <line x1="220" y1="40" x2="220" y2="230" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
                <line x1="340" y1="40" x2="340" y2="230" stroke="rgba(255,255,255,0.06)" stroke-width="1" />

                <!-- Axes -->
                <line x1="40" y1="180" x2="400" y2="180" stroke="#cbd5e1" stroke-width="2.5" />
                <polygon points="405,180 395,176 395,184" fill="#cbd5e1" />
                <text x="408" y="184" fill="#cbd5e1" font-size="11" font-weight="bold">x</text>

                <line x1="160" y1="230" x2="160" y2="40" stroke="#cbd5e1" stroke-width="2.5" />
                <polygon points="160,35 156,45 164,45" fill="#cbd5e1" />
                <text x="160" y="28" fill="#cbd5e1" font-size="11" font-weight="bold" text-anchor="middle">y</text>
                <text x="148" y="195" fill="#94a3b8" font-size="10">O(0,0)</text>

                <!-- Axis of Symmetry x = p -->
                <line x1="260" y1="40" x2="260" y2="230" stroke="#f43f5e" stroke-width="1.5" stroke-dasharray="4,4" />
                <text x="260" y="244" fill="#f43f5e" font-size="9.5" font-weight="bold" text-anchor="middle">Axis of Symmetry (x = p)</text>

                <!-- Parabola Curve y = a(x - p)^2 + q (a > 0, smiling curve) -->
                <path d="M 120 70 Q 260 270 400 70" fill="none" stroke="#38bdf8" stroke-width="3.5" stroke-linecap="round" />

                <!-- Turning Point (Vertex) -->
                <circle cx="260" cy="170" r="5" fill="#facc15" stroke="#ca8a04" stroke-width="1.5" />
                <text x="270" y="165" fill="#fef08a" font-size="10.5" font-weight="bold">Turning Point (p, q)</text>

                <!-- X-Intercepts (Roots) -->
                <circle cx="180" cy="180" r="4.5" fill="#10b981" />
                <text x="175" y="168" fill="#6ee7b7" font-size="9.5" font-weight="bold">x₁</text>
                <circle cx="340" cy="180" r="4.5" fill="#10b981" />
                <text x="345" y="168" fill="#6ee7b7" font-size="9.5" font-weight="bold">x₂</text>

                <!-- Y-Intercept -->
                <circle cx="160" cy="120" r="4.5" fill="#ec4899" />
                <text x="135" y="122" fill="#f472b6" font-size="9.5" font-weight="bold">y-int (0, c)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Standard Cartesian Parabola with Turning Point, Symmetry & Intercepts</p>
        </div>
        """

    elif diagram_type == "business_environments":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 310" width="100%" style="max-width: 480px; height: auto; background: rgba(234,179,8,0.05); border-radius: 16px; border: 1.5px solid rgba(234,179,8,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="24" fill="#fbbf24" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">THE THREE BUSINESS ENVIRONMENTS (CAPS DBE)</text>
                
                <!-- Macro Environment (Outer Ring) -->
                <circle cx="220" cy="165" r="125" fill="rgba(239,68,68,0.15)" stroke="#ef4444" stroke-width="2" />
                <text x="220" y="55" fill="#fca5a5" font-size="11" font-weight="bold" text-anchor="middle">MACRO ENVIRONMENT (No Control - PESTLE)</text>
                <text x="220" y="68" fill="#f87171" font-size="8.5" text-anchor="middle">Political, Economic, Social, Technological, Legal, Environmental</text>

                <!-- Market Environment (Middle Ring) -->
                <circle cx="220" cy="165" r="85" fill="rgba(245,158,11,0.2)" stroke="#f59e0b" stroke-width="2" />
                <text x="220" y="100" fill="#fef08a" font-size="10.5" font-weight="bold" text-anchor="middle">MARKET ENVIRONMENT (Some Influence)</text>
                <text x="220" y="112" fill="#fbbf24" font-size="8.5" text-anchor="middle">Consumers, Competitors, Suppliers, Intermediaries</text>

                <!-- Micro Environment (Inner Core) -->
                <circle cx="220" cy="165" r="48" fill="rgba(16,185,129,0.3)" stroke="#10b981" stroke-width="2.5" />
                <text x="220" y="155" fill="#ffffff" font-size="11" font-weight="bold" text-anchor="middle">MICRO</text>
                <text x="220" y="168" fill="#a7f3d0" font-size="8.5" font-weight="bold" text-anchor="middle">Full Control</text>
                <text x="220" y="180" fill="#6ee7b7" font-size="7.5" text-anchor="middle">Vision, Missions, 8 Depts</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Micro, Market, and Macro Business Environments & Control Levels</p>
        </div>
        """

    elif diagram_type == "economic_circular_flow":
        return """
        <div style="text-align: center; margin: 16px 0;">
            <svg viewBox="0 0 440 280" width="100%" style="max-width: 480px; height: auto; background: rgba(16,185,129,0.05); border-radius: 16px; border: 1.5px solid rgba(16,185,129,0.4); box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <text x="220" y="24" fill="#34d399" font-size="13" font-weight="900" text-anchor="middle" letter-spacing="1">MACROECONOMIC CIRCULAR FLOW MODEL</text>
                
                <!-- Households Box (Left) -->
                <rect x="30" y="105" width="95" height="70" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="2" />
                <text x="77" y="135" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">HOUSEHOLDS</text>
                <text x="77" y="150" fill="#94a3b8" font-size="8.5" text-anchor="middle">Owners of Factors</text>

                <!-- Businesses / Firms Box (Right) -->
                <rect x="315" y="105" width="95" height="70" rx="10" fill="#1e293b" stroke="#f59e0b" stroke-width="2" />
                <text x="362" y="135" fill="#f59e0b" font-size="11" font-weight="bold" text-anchor="middle">BUSINESSES</text>
                <text x="362" y="150" fill="#94a3b8" font-size="8.5" text-anchor="middle">Producers of Goods</text>

                <!-- Goods / Product Market (Top) -->
                <rect x="155" y="45" width="130" height="42" rx="8" fill="#0f172a" stroke="#10b981" stroke-width="1.5" />
                <text x="220" y="65" fill="#34d399" font-size="10.5" font-weight="bold" text-anchor="middle">GOODS & SERVICES</text>
                <text x="220" y="78" fill="#6ee7b7" font-size="8.5" text-anchor="middle">Product Market</text>

                <!-- Factor / Resource Market (Bottom) -->
                <rect x="155" y="195" width="130" height="42" rx="8" fill="#0f172a" stroke="#a855f7" stroke-width="1.5" />
                <text x="220" y="215" fill="#c084fc" font-size="10.5" font-weight="bold" text-anchor="middle">FACTOR MARKET</text>
                <text x="220" y="228" fill="#d8b4fe" font-size="8.5" text-anchor="middle">Labour, Land, Capital</text>

                <!-- Circular Flow Arrows -->
                <path d="M 80 105 Q 80 65 150 65" fill="none" stroke="#10b981" stroke-width="2.5" />
                <path d="M 290 65 Q 360 65 360 105" fill="none" stroke="#10b981" stroke-width="2.5" />
                <path d="M 360 175 Q 360 215 290 215" fill="none" stroke="#a855f7" stroke-width="2.5" />
                <path d="M 150 215 Q 80 215 80 175" fill="none" stroke="#a855f7" stroke-width="2.5" />

                <!-- Flow Labels -->
                <text x="220" y="105" fill="#10b981" font-size="9" font-weight="bold" text-anchor="middle">Spending for Goods (Rands) ➔</text>
                <text x="220" y="185" fill="#a855f7" font-size="9" font-weight="bold" text-anchor="middle">⮜ Wages, Rent, Interest & Profit</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.85; margin-top: 6px; font-weight: bold;">Figure: Two-Sector Circular Flow between Households & Firms (CAPS Economics & EMS)</p>
        </div>
        """


    elif diagram_type == "atom_model":
        element = data.get("element", "Carbon (C)")
        protons = data.get("protons", 6)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 240 180" width="260" height="180" style="background: rgba(6,182,212,0.06); border-radius: 12px; border: 1px dashed #06b6d4;">
                <circle cx="120" cy="90" r="18" fill="rgba(239,68,68,0.4)" stroke="#ef4444" stroke-width="2" />
                <text x="120" y="93" fill="#ffffff" font-size="10" font-weight="bold" text-anchor="middle">{protons}p⁺ {protons}n⁰</text>
                <!-- Inner shell (2 electrons) -->
                <circle cx="120" cy="90" r="42" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="3,3" />
                <circle cx="120" cy="48" r="3.5" fill="#38bdf8" />
                <circle cx="120" cy="132" r="3.5" fill="#38bdf8" />
                <!-- Outer shell -->
                <circle cx="120" cy="90" r="70" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4,4" />
                <circle cx="50" cy="90" r="3.5" fill="#06b6d4" />
                <circle cx="190" cy="90" r="3.5" fill="#06b6d4" />
                <circle cx="120" cy="20" r="3.5" fill="#06b6d4" />
                <circle cx="120" cy="160" r="3.5" fill="#06b6d4" />
                <text x="120" y="174" fill="#38bdf8" font-size="10" font-weight="bold" text-anchor="middle">{element} Bohr Model</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Rutherford-Bohr Atomic Shell Diagram</p>
        </div>
        """

    elif diagram_type == "accounting_scale":
        assets = data.get("assets", 150000)
        equity = data.get("equity", 90000)
        liab = data.get("liabilities", 60000)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 320 150" width="320" height="150" style="background: rgba(234,179,8,0.06); border-radius: 12px; border: 1px dashed #eab308;">
                <polygon points="160,30 150,120 170,120" fill="#64748b" />
                <line x1="50" y1="50" x2="270" y2="50" stroke="#f59e0b" stroke-width="4" stroke-linecap="round" />
                <circle cx="160" cy="50" r="6" fill="#eab308" />
                <!-- Left pan (Assets) -->
                <line x1="50" y1="50" x2="35" y2="90" stroke="#94a3b8" stroke-width="1.5" />
                <line x1="50" y1="50" x2="65" y2="90" stroke="#94a3b8" stroke-width="1.5" />
                <ellipse cx="50" cy="90" rx="32" ry="7" fill="#3b82f6" opacity="0.4" stroke="#3b82f6" stroke-width="2" />
                <text x="50" y="112" fill="#60a5fa" font-size="10" font-weight="bold" text-anchor="middle">Assets (A)</text>
                <text x="50" y="125" fill="#93c5fd" font-size="9" text-anchor="middle">R{assets:,}</text>
                <!-- Right pan (Equity + Liabilities) -->
                <line x1="270" y1="50" x2="255" y2="90" stroke="#94a3b8" stroke-width="1.5" />
                <line x1="270" y1="50" x2="285" y2="90" stroke="#94a3b8" stroke-width="1.5" />
                <ellipse cx="270" cy="90" rx="36" ry="7" fill="#10b981" opacity="0.4" stroke="#10b981" stroke-width="2" />
                <text x="270" y="112" fill="#34d399" font-size="10" font-weight="bold" text-anchor="middle">O + L</text>
                <text x="270" y="125" fill="#a7f3d0" font-size="9" text-anchor="middle">R{equity:,} + R{liab:,}</text>
                <!-- Scale Base -->
                <rect x="130" y="120" width="60" height="8" rx="3" fill="#475569" />
                <text x="160" y="22" fill="#facc15" font-size="11" font-weight="bold" text-anchor="middle">The Accounting Equation: Assets = Equity + Liabilities</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Accounting Equation Balance Scale ($A = O + L$)</p>
        </div>
        """

    elif diagram_type == "supply_demand":
        pe = data.get("pe", 50)
        qe = data.get("qe", 100)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 260 160" width="280" height="160" style="background: rgba(168,85,247,0.06); border-radius: 12px; border: 1px dashed #a855f7;">
                <!-- Axes -->
                <line x1="40" y1="130" x2="240" y2="130" stroke="#94a3b8" stroke-width="2" />
                <line x1="40" y1="130" x2="40" y2="20" stroke="#94a3b8" stroke-width="2" />
                <text x="35" y="25" fill="#e2e8f0" font-size="10" font-weight="bold" text-anchor="end">Price (P)</text>
                <text x="235" y="145" fill="#e2e8f0" font-size="10" font-weight="bold">Qty (Q)</text>
                <!-- Demand Curve (downward) -->
                <line x1="50" y1="35" x2="210" y2="125" stroke="#f43f5e" stroke-width="2.5" />
                <text x="215" y="125" fill="#f43f5e" font-size="11" font-weight="bold">D</text>
                <!-- Supply Curve (upward) -->
                <line x1="50" y1="125" x2="210" y2="35" stroke="#10b981" stroke-width="2.5" />
                <text x="215" y="38" fill="#10b981" font-size="11" font-weight="bold">S</text>
                <!-- Equilibrium Point -->
                <circle cx="130" cy="80" r="5" fill="#eab308" />
                <line x1="40" y1="80" x2="130" y2="80" stroke="#eab308" stroke-dasharray="3,3" />
                <line x1="130" y1="80" x2="130" y2="130" stroke="#eab308" stroke-dasharray="3,3" />
                <text x="35" y="83" fill="#eab308" font-size="9" text-anchor="end">P* = {pe}</text>
                <text x="130" y="145" fill="#eab308" font-size="9" text-anchor="middle">Q* = {qe}</text>
                <text x="140" y="72" fill="#facc15" font-size="10" font-weight="bold">Equilibrium (E)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Market Supply and Demand Equilibrium</p>
        </div>
        """

    elif diagram_type == "contour_map":
        h_outer = data.get("h_outer", 500)
        h_mid = data.get("h_mid", 600)
        h_peak = data.get("h_peak", 750)
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 260 160" width="280" height="160" style="background: rgba(234,179,8,0.06); border-radius: 12px; border: 1px dashed #eab308;">
                <!-- Outer contour -->
                <ellipse cx="130" cy="80" rx="105" ry="60" fill="none" stroke="#d97706" stroke-width="1.5" />
                <text x="25" y="85" fill="#f59e0b" font-size="9">{h_outer}m</text>
                <!-- Mid contour -->
                <ellipse cx="130" cy="80" rx="70" ry="40" fill="none" stroke="#d97706" stroke-width="2" />
                <text x="62" y="85" fill="#f59e0b" font-size="9">{h_mid}m</text>
                <!-- Inner peak contour -->
                <ellipse cx="130" cy="80" rx="35" ry="20" fill="rgba(245,158,11,0.2)" stroke="#b45309" stroke-width="2.5" />
                <circle cx="130" cy="80" r="2.5" fill="#f43f5e" />
                <text x="130" y="74" fill="#fef08a" font-size="9" font-weight="bold" text-anchor="middle">▲ {h_peak}m</text>
                <text x="130" y="150" fill="#94a3b8" font-size="9" text-anchor="middle">Concentric contour lines indicate a hill / knoll</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Topographic Map Contour Lines (1:50 000 Scale)</p>
        </div>
        """

    elif diagram_type == "lever_diagram":
        class_type = data.get("class", "Class 1")
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 280 130" width="290" height="130" style="background: rgba(244,63,94,0.06); border-radius: 12px; border: 1px dashed #f43f5e;">
                <!-- Beam -->
                <line x1="30" y1="60" x2="250" y2="60" stroke="#cbd5e1" stroke-width="5" stroke-linecap="round" />
                <!-- Fulcrum (Triangle in middle) -->
                <polygon points="140,65 125,95 155,95" fill="#f59e0b" stroke="#d97706" stroke-width="1.5" />
                <text x="140" y="110" fill="#f59e0b" font-size="10" font-weight="bold" text-anchor="middle">Fulcrum (Pivot)</text>
                <!-- Effort arrow left (downwards) -->
                <line x1="50" y1="25" x2="50" y2="55" stroke="#10b981" stroke-width="3" />
                <polygon points="50,60 45,52 55,52" fill="#10b981" />
                <text x="50" y="20" fill="#10b981" font-size="10" font-weight="bold" text-anchor="middle">Effort (F)</text>
                <!-- Load box right -->
                <rect x="220" y="35" width="25" height="25" fill="#6366f1" stroke="#4f46e5" stroke-width="1.5" rx="3" />
                <text x="232" y="52" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">Load</text>
                <text x="140" y="20" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">{class_type} Lever: Fulcrum between Effort & Load</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Mechanical Lever System (Mechanical Advantage = Load / Effort)</p>
        </div>
        """

    elif diagram_type == "physics_free_body":
        mass = data.get("mass", "15 kg")
        f_app = data.get("appliedForce", "80 N")
        f_f = data.get("friction", "30 N")
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 260 150" width="270" height="150" style="background: rgba(245,158,11,0.06); border-radius: 12px; border: 1px dashed #f59e0b;">
                <line x1="10" y1="110" x2="250" y2="110" stroke="#71717a" stroke-width="2" />
                <rect x="95" y="60" width="70" height="50" fill="rgba(59, 130, 246, 0.25)" stroke="#3b82f6" stroke-width="2" rx="4" />
                <text x="130" y="90" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">{mass}</text>
                <line x1="165" y1="85" x2="225" y2="85" stroke="#f59e0b" stroke-width="2.5" />
                <polygon points="232,85 224,81 224,89" fill="#f59e0b" />
                <text x="195" y="75" fill="#f59e0b" font-size="10" font-weight="bold">F_app = {f_app}</text>
                <line x1="95" y1="85" x2="35" y2="85" stroke="#a855f7" stroke-width="2.5" />
                <polygon points="28,85 36,81 36,89" fill="#a855f7" />
                <text x="45" y="75" fill="#a855f7" font-size="10" font-weight="bold">f_k = {f_f}</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Free-Body Diagram ($F_{{net}} = m \\cdot a$)</p>
        </div>
        """

    elif diagram_type == "biology_punnett":
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <table style="margin: 0 auto; border-collapse: collapse; font-family: monospace; font-size: 13px; text-align: center;">
                <tr><td style="padding: 6px; color: #94a3b8;">♀ \\ ♂</td><td style="padding: 6px; background: rgba(244,63,94,0.2); font-weight: bold;">B</td><td style="padding: 6px; background: rgba(244,63,94,0.2); font-weight: bold;">b</td></tr>
                <tr><td style="padding: 6px; background: rgba(99,102,241,0.2); font-weight: bold;">B</td><td style="padding: 6px; border: 1px solid #6366f1; color: #facc15;">BB (25%)</td><td style="padding: 6px; border: 1px solid #6366f1; color: #facc15;">Bb (25%)</td></tr>
                <tr><td style="padding: 6px; background: rgba(99,102,241,0.2); font-weight: bold;">b</td><td style="padding: 6px; border: 1px solid #6366f1; color: #facc15;">Bb (25%)</td><td style="padding: 6px; border: 1px solid #6366f1; color: #4ade80;">bb (25%)</td></tr>
            </table>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: 2x2 Punnett Square (Genotype Ratio: 1 BB : 2 Bb : 1 bb)</p>
        </div>
        """

    elif diagram_type == "accounting_t_account":
        acc_name = data.get("name", "Bank Account")
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 280 120" width="290" height="120" style="background: rgba(16,185,129,0.06); border-radius: 12px; border: 1px dashed #10b981;">
                <text x="140" y="24" fill="#34d399" font-size="12" font-weight="bold" text-anchor="middle">General Ledger: {acc_name}</text>
                <text x="35" y="42" fill="#e2e8f0" font-size="11" font-weight="bold">Debit (Dr)</text>
                <text x="245" y="42" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="end">Credit (Cr)</text>
                <!-- T-shape bar -->
                <line x1="20" y1="48" x2="260" y2="48" stroke="#10b981" stroke-width="2.5" />
                <line x1="140" y1="48" x2="140" y2="105" stroke="#10b981" stroke-width="2.5" />
                <text x="45" y="70" fill="#a7f3d0" font-size="10">Receipts (+) [CRJ]</text>
                <text x="165" y="70" fill="#fca5a5" font-size="10">Payments (-) [CPJ]</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: General Ledger T-Account Standard Format</p>
        </div>
        """

    elif diagram_type == "swot_matrix":
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 280 150" width="280" height="150" style="background: rgba(99,102,241,0.06); border-radius: 12px; border: 1px dashed #6366f1;">
                <rect x="25" y="25" width="110" height="55" fill="rgba(16,185,129,0.2)" stroke="#10b981" stroke-width="1.5" rx="4" />
                <text x="80" y="55" fill="#34d399" font-size="12" font-weight="bold" text-anchor="middle">Strengths (S)</text>
                <rect x="145" y="25" width="110" height="55" fill="rgba(239,68,68,0.2)" stroke="#ef4444" stroke-width="1.5" rx="4" />
                <text x="200" y="55" fill="#f87171" font-size="12" font-weight="bold" text-anchor="middle">Weaknesses (W)</text>
                <rect x="25" y="85" width="110" height="55" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" stroke-width="1.5" rx="4" />
                <text x="80" y="115" fill="#60a5fa" font-size="12" font-weight="bold" text-anchor="middle">Opportunities (O)</text>
                <rect x="145" y="85" width="110" height="55" fill="rgba(245,158,11,0.2)" stroke="#f59e0b" stroke-width="1.5" rx="4" />
                <text x="200" y="115" fill="#fbbf24" font-size="12" font-weight="bold" text-anchor="middle">Threats (T)</text>
                <text x="80" y="18" fill="#94a3b8" font-size="9" text-anchor="middle">INTERNAL (Controlled)</text>
                <text x="200" y="18" fill="#94a3b8" font-size="9" text-anchor="middle">EXTERNAL (Macro)</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: 2x2 SWOT Analysis Strategic Framework</p>
        </div>
        """

    elif diagram_type == "cartoon_analysis":
        speech = data.get("speech", "Don't worry, the test is totally easy!")
        character = data.get("character", "Smirking Student")
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 300 140" width="310" height="140" style="background: rgba(168,85,247,0.06); border-radius: 12px; border: 1px dashed #a855f7;">
                <!-- Speech bubble -->
                <rect x="20" y="15" width="190" height="55" rx="8" fill="#ffffff" stroke="#a855f7" stroke-width="2" />
                <polygon points="120,70 140,70 115,85" fill="#ffffff" />
                <polygon points="120,70 140,70 115,85" stroke="#a855f7" stroke-width="1.5" />
                <text x="115" y="38" fill="#1e1b4b" font-size="10" font-weight="bold" text-anchor="middle">"{speech}"</text>
                <text x="115" y="52" fill="#6b21a8" font-size="9" text-anchor="middle">[Visual irony / Sarcasm indicator]</text>
                <!-- Character face -->
                <circle cx="245" cy="70" r="30" fill="rgba(244,63,94,0.25)" stroke="#f43f5e" stroke-width="2" />
                <!-- Eyes & smirk -->
                <circle cx="235" cy="62" r="3.5" fill="#f43f5e" />
                <circle cx="255" cy="62" r="3.5" fill="#f43f5e" />
                <path d="M 235 80 Q 245 92 260 76" fill="none" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" />
                <text x="245" y="118" fill="#f43f5e" font-size="9" font-weight="bold" text-anchor="middle">{character}</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Visual Literacy & Editorial Cartoon Panel</p>
        </div>
        """

    elif diagram_type == "tariff_graph":
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 280 140" width="290" height="140" style="background: rgba(6,182,212,0.06); border-radius: 12px; border: 1px dashed #06b6d4;">
                <line x1="40" y1="115" x2="260" y2="115" stroke="#94a3b8" stroke-width="2" />
                <line x1="40" y1="115" x2="40" y2="20" stroke="#94a3b8" stroke-width="2" />
                <text x="35" y="25" fill="#e2e8f0" font-size="9" font-weight="bold" text-anchor="end">Cost (R)</text>
                <text x="240" y="130" fill="#e2e8f0" font-size="9" font-weight="bold">Usage (kL / kWh)</text>
                <!-- Step blocks -->
                <line x1="40" y1="95" x2="100" y2="95" stroke="#10b981" stroke-width="3" />
                <text x="70" y="88" fill="#34d399" font-size="9">Block 1: R15/kL</text>
                <line x1="100" y1="95" x2="100" y2="70" stroke="#10b981" stroke-width="1.5" stroke-dasharray="2,2" />
                <line x1="100" y1="70" x2="180" y2="70" stroke="#eab308" stroke-width="3" />
                <text x="140" y="63" fill="#facc15" font-size="9">Block 2: R25/kL</text>
                <line x1="180" y1="70" x2="180" y2="40" stroke="#eab308" stroke-width="1.5" stroke-dasharray="2,2" />
                <line x1="180" y1="40" x2="250" y2="40" stroke="#ef4444" stroke-width="3" />
                <text x="215" y="33" fill="#f87171" font-size="9">Block 3: R40/kL</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: Municipal Stepped Tariff Block Graph</p>
        </div>
        """

    elif diagram_type == "smart_goals":
        return f"""
        <div style="text-align: center; margin: 12px 0;">
            <svg viewBox="0 0 300 100" width="310" height="100" style="background: rgba(16,185,129,0.06); border-radius: 12px; border: 1px dashed #10b981;">
                <circle cx="35" cy="50" r="22" fill="rgba(16,185,129,0.2)" stroke="#10b981" stroke-width="2" />
                <text x="35" y="55" fill="#34d399" font-size="12" font-weight="bold" text-anchor="middle">S</text>
                <circle cx="95" cy="50" r="22" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" stroke-width="2" />
                <text x="95" y="55" fill="#60a5fa" font-size="12" font-weight="bold" text-anchor="middle">M</text>
                <circle cx="155" cy="50" r="22" fill="rgba(234,179,8,0.2)" stroke="#eab308" stroke-width="2" />
                <text x="155" y="55" fill="#facc15" font-size="12" font-weight="bold" text-anchor="middle">A</text>
                <circle cx="215" cy="50" r="22" fill="rgba(168,85,247,0.2)" stroke="#a855f7" stroke-width="2" />
                <text x="215" y="55" fill="#c084fc" font-size="12" font-weight="bold" text-anchor="middle">R</text>
                <circle cx="275" cy="50" r="22" fill="rgba(244,63,94,0.2)" stroke="#f43f5e" stroke-width="2" />
                <text x="275" y="55" fill="#fb7185" font-size="12" font-weight="bold" text-anchor="middle">T</text>
                <text x="155" y="90" fill="#94a3b8" font-size="9" text-anchor="middle">Specific • Measurable • Achievable • Relevant • Time-Bound</text>
            </svg>
            <p style="font-size: 11px; opacity: 0.8; margin-top: 4px;">Figure: SMART Goal Setting Framework</p>
        </div>
        """
# Exact text labels inside each SVG that should be hidden in quiz mode
DIAGRAM_LABELS_TO_HIDE = {
    "human_digestive": [
        "Stomach", "Liver (Bile Production)", "Gallbladder (Stores Bile)",
        "Esophagus (Peristalsis)", "Salivary Glands (Amylase)",
        "Small Intestine (Ileum)", "Villi Nutrient Absorption",
        "Large Intestine (Colon)", "Water & Mineral Reabsorption",
        "Pancreas (Lipase/Insulin)", "Rectum & Anus (Egestion)",
    ],
    "human_heart": [
        "Right Atrium", "Left Atrium", "Right Ventricle", "Left Ventricle",
        "Thick Myocardium", "RA", "LA", "RV", "LV",
        "Superior Vena Cava (Inflow)", "Systemic Aorta (High Pressure)",
        "Tricuspid Valve", "Bicuspid (Mitral) Valve",
    ],
    "plant_cell": [
        "Nucleus & DNA", "Large Central Vacuole",
        "(Cell Sap & Turgor Pressure)", "Chloroplast (Grana)",
        "Mitochondrion (ATP)", "Cellulose Cell Wall",
    ],
    "electric_circuit": [
        "Battery (V = 12V)", "Closed Switch (S)", "Ammeter (I)",
        "Resistor R = 6 Ω", "Voltmeter in Parallel", "Current (I)",
    ],
    "atom_model": [
        "6p⁺ 6n⁰", "Carbon (C) Bohr Model",
    ],
    "lever_diagram": [
        "Fulcrum (Pivot)", "Effort (F)", "Load",
        "Class 1 Lever: Fulcrum between Effort & Load",
    ],
    "pythagoras": [
        "a = 3", "b = 4", "c (hyp) = 5",
    ],
    "contour_map": [
        "▲ 750m", "500m", "600m",
    ],
    "accounting_scale": [
        "Assets (A)", "O + L",
    ],
    "supply_demand": [
        "Equilibrium (E)", "D", "S",
    ],
    "physics_free_body": [
        "F_app = 80 N", "f_k = 30 N", "15 kg",
    ],
    "cartesian_parabola": [
        "Turning Point (p, q)", "y-int (0, c)", "Axis of Symmetry (x = p)",
    ],
    "biology_punnett": [],  # Punnett square labels are the actual content
}


def hide_diagram_labels(svg_html, labels):
    """Blank out specific text labels in an SVG for quiz mode."""
    if not labels:
        return svg_html
    result = svg_html
    for label in labels:
        # Match <text ...>LABEL</text> and replace the label with spaces
        pattern = r'(<text[^>]*>)\s*' + re.escape(label) + r'\s*(</text>)'
        result = re.sub(pattern, r'\1 \2', result, flags=re.IGNORECASE)
    return result
    # Generic fallback diagram for any other case
    return f"""
    <div style="text-align: center; margin: 12px 0;">
        <svg viewBox="0 0 260 80" width="280" height="80" style="background: rgba(255,255,255,0.04); border-radius: 12px; border: 1px dashed rgba(255,255,255,0.2);">
            <text x="130" y="45" fill="#94a3b8" font-size="12" font-weight="bold" text-anchor="middle">CAPS Diagnostic Visual</text>
        </svg>
    </div>
    """
def add_quiz_markers(svg_html, spots):
    """Inject numbered pink dots into an SVG string."""
    if not spots:
        return svg_html

    markers = ""
    for spot in spots:
        markers += f'''
        <circle cx="{spot['x']}" cy="{spot['y']}" r="14" fill="#ff007f" stroke="#ffffff" stroke-width="2" opacity="0.95" />
        <text x="{spot['x']}" y="{spot['y'] + 5}" fill="#ffffff" font-size="14" font-weight="bold" text-anchor="middle">{spot['id']}</text>
        '''

    return svg_html.replace("</svg>", markers + "</svg>")


def ask_ai_diagram_question(diagram_type, labeled_parts, subject_name, grade, tone):
    """Ask AI to generate a bonus question about a diagram."""
    parts_str = ", ".join(labeled_parts)

    system_prompt = f"""You are a CAPS exam question writer for Grade {grade} {subject_name}.
The student just studied a diagram containing these parts: {parts_str}.

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

Generate ONE diagram-related exam question. Return ONLY valid JSON:
{{
  "question": "<the question, referencing the diagram parts>",
  "correct": "<short correct answer>",
  "steps": ["<step 1>", "<step 2>"],
  "hint": "<a hint in the requested tone>"
}}

Rules:
- The question MUST relate to the diagram parts listed.
- Answer should be SHORT and easy to type (a word, number, or short phrase).
- Real CAPS context — the kind of thing DBE actually asks.
- Return ONLY the JSON object."""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": system_prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    result = json.loads(response.choices[0].message.content)

    # Safety: unwrap if AI returned a list
    if isinstance(result, list):
        result = result[0] if result else {}

    # Safety: fix malformed sections (strings → dicts, non-dict questions removed)
    if isinstance(result, dict) and "sections" in result:
        fixed_sections = []
        for section in result["sections"]:
            if isinstance(section, str):
                # Turn a stray string into a section with a placeholder question
                fixed_sections.append({
                    "name": section,
                    "marks": 0,
                    "questions": []
                })
            elif isinstance(section, dict):
                # Filter out non-dict questions
                section["questions"] = [
                    q for q in section.get("questions", []) if isinstance(q, dict)
                ]
                fixed_sections.append(section)
        result["sections"] = fixed_sections

    return result
    
# ---------------------------------------------------------
# 5. PROCEDURAL QUESTION GENERATORS WITH ALL 3 TONE MODES
def generate_lockin_question(subject_id, grade, active_topic, tone_mode):
    """Generate dynamic questions with authentic CAPS content, written math, and diagrams."""
    q_id = f"{subject_id}-{grade}-{random.randint(1000, 9999)}"

    # ============ AI QUESTION POOL (try this first) ============
    ai_pool = (
        AI_GENERATED_QUESTIONS
        .get(subject_id, {})
        .get(str(grade), {})
        .get(active_topic, [])
    )
    if ai_pool:
        ai_q = random.choice(ai_pool).copy()
        ai_q["id"] = q_id
        if not ai_q.get("diagram"):
            ai_q["diagram"] = topic_to_diagram(active_topic, subject_id)
        ai_q.setdefault("diagram_data", {})
        return ai_q
    # ============ END AI POOL ============

    # 1. Mathematics
    if subject_id == "mathematics":
        if "Integer" in active_topic:
            sub_type = random.choice([1, 2])
            if sub_type == 1:
                a = random.randint(3, 11)
                b = random.randint(2, 9)
                ans = -a + b
                return {
                    "id": q_id, "grade": grade, "subject": "Mathematics",
                    "topic": "Integers", "subtopic": "Subtracting Negative Integers",
                    "question": "Calculate the value of the signed integer expression using written rules:",
                    "math_expression": rf"(-{a}) - (-{b})",
                    "correct": str(ans),
                    "steps": [
                        rf"Step 1: Sign rule: subtracting a negative is adding a positive: $-(-{b}) = +{b}$",
                        rf"Step 2: Rewrite in standard written form: $= -{a} + {b}$",
                        rf"Step 3: Move on number line (start at $-{a}$, jump right ${b}$ units): $= {ans}$"
                    ],
                    "diagram": "number_line",
                    "diagram_data": {"start": -a, "jump": b, "end": ans},
                    "hints": {
                        "tiktok": f"Minus next to a minus is a PLUS, no cap! $-(-{b}) = +{b}$. Slide right on the number line!",
                        "casual": f"Two minuses together turn into a plus sign (+). So calculate -{a} + {b}!",
                        "formal": f"Apply additive inverse: $a - (-b) = a + b$. Evaluate the algebraic sum."
                    },
                    "cheers": {
                        "tiktok": "W rizz on negative numbers! You locked in on the double minus rule! 🔥",
                        "casual": "Great job! You handled the signed integers like a pro! 🎯",
                        "formal": "Correct. Signed integer property accurately computed."
                    }
                }
            else:
                a = random.randint(3, 8)
                b = random.randint(2, 7)
                ans = a * b
                return {
                    "id": q_id, "grade": grade, "subject": "Mathematics",
                    "topic": "Integers", "subtopic": "Multiplying Negative Integers",
                    "question": "Multiply the signed integers using written multiplication rules:",
                    "math_expression": rf"(-{a}) \times (-{b})",
                    "correct": str(ans),
                    "steps": [
                        r"Step 1: Sign rule for multiplication: $\text{Negative} \times \text{Negative} = \text{Positive (+)}$",
                        rf"Step 2: Multiply the values: ${a} \times {b} = {ans}$",
                        rf"Step 3: Final written answer: $= {ans}$"
                    ],
                    "diagram": "number_line",
                    "diagram_data": {"start": 0, "jump": ans, "end": ans},
                    "hints": {
                        "tiktok": f"Negative times negative is positive, period! Multiply {a} and {b}!",
                        "casual": f"Same signs multiply to give a positive result! Just do {a} × {b}!",
                        "formal": r"Product of two negative integers is strictly positive: $(-a) \cdot (-b) = +ab$."
                    },
                    "cheers": {
                        "tiktok": "Bro cooked! Negative times negative is a whole W! 💅",
                        "casual": "Spot on! You remembered the multiplication sign rule! ✨",
                        "formal": "Correct. Law of integer multiplication signs satisfied."
                    }
                }

        elif "Fraction" in active_topic:
            pairs = [
                (1, 2, 1, 4, 4, 2, 1, 3, 4, "3/4"),
                (2, 3, 1, 6, 6, 2, 1, 5, 6, "5/6"),
                (1, 3, 1, 2, 6, 2, 3, 5, 6, "5/6"),
                (3, 4, 1, 8, 8, 2, 1, 7, 8, "7/8"),
            ]
            n1, d1, n2, d2, lcd, m1, m2, aNum, aDen, aStr = random.choice(pairs)
            eq1 = n1 * m1
            eq2 = n2 * m2
            return {
                "id": q_id, "grade": grade, "subject": "Mathematics",
                "topic": "Common Fractions", "subtopic": "Addition of Fractions (Written Standard)",
                "question": "Calculate the sum of the common fractions in simplest written form:",
                "math_expression": rf"\frac{{{n1}}}{{{d1}}} + \frac{{{n2}}}{{{d2}}}",
                "correct": aStr,
                "steps": [
                    rf"Step 1: Find Lowest Common Denominator (LCD) of ${d1}$ and ${d2}$: $\text{{LCD}} = {lcd}$",
                    rf"Step 2: Convert to equivalent fractions: $\frac{{{eq1}}}{{{lcd}}} + \frac{{{eq2}}}{{{lcd}}}$",
                    rf"Step 3: Add the numerators over the common denominator: $\frac{{{aNum}}}{{{aDen}}}$"
                ],
                "diagram": "fraction_model",
                "diagram_data": {"num": aNum, "den": aDen, "label": f"{aNum}/{aDen}"},
                "hints": {
                    "tiktok": f"Denominators aren't matching! Bring them both over {lcd}, then add the top numbers!",
                    "casual": f"Find the common denominator ({lcd}) first, convert both fractions, then add numerators!",
                    "formal": f"Determine the LCM of denominators before calculating sum of numerators."
                },
                "cheers": {
                    "tiktok": "Sheesh! Stacked fractions master! That was clean! ✨",
                    "casual": "Lekker work! You solved the fraction addition cleanly! 🚀",
                    "formal": "Correct. Fraction addition with lowest common denominator properly performed."
                }
            }

        elif "Pythagoras" in active_topic:
            triples = [(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17)]
            a, b, c = random.choice(triples)
            return {
                "id": q_id, "grade": grade, "subject": "Mathematics",
                "topic": "Theorem of Pythagoras", "subtopic": "Calculating Hypotenuse",
                "question": f"In right-angled triangle ABC, the legs have lengths a = {a} cm and b = {b} cm. Calculate the length of the hypotenuse c (in cm).",
                "correct": str(c),
                "steps": [
                    f"State theorem: c^2 = a^2 + b^2 [Pythagoras]",
                    f"Substitute: c^2 = {a}^2 + {b}^2 = {a*a} + {b*b} = {c*c}",
                    f"Square root: c = sqrt({c*c}) = {c} cm"
                ],
                "diagram": "pythagoras",
                "diagram_data": {"a": a, "b": b, "c": c},
                "hints": {
                    "tiktok": f"Square {a} and {b}, add them up, then take the root. Easy claps!",
                    "casual": f"Square both sides: {a}² + {b}² = {a*a + b*b}, then take the square root!",
                    "formal": "Apply the Theorem of Pythagoras: c² = a² + b²."
                },
                "cheers": {
                    "tiktok": "Bro cooked! That's a whole W on Pythagoras fr fr! 💅🔥",
                    "casual": "Lekker job! You nailed that hypotenuse question! 🚀",
                    "formal": "Correct. Your application of the geometric theorem is mathematically sound."
                }
            }
        else:
            angle = random.choice([65, 70, 75, 110, 115, 120])
            ans = 180 - angle
            return {
                "id": q_id, "grade": grade, "subject": "Mathematics",
                "topic": "Geometry of Straight Lines", "subtopic": "Adjacent Angles on a Line",
                "question": f"In the diagram, straight line AB has adjacent angles measuring x and {angle}°. Determine the value of x.",
                "correct": str(ans),
                "steps": [
                    f"Adjacent angles on a straight line equal 180°: x + {angle}° = 180°",
                    f"Subtract: x = 180° - {angle}° = {ans}°"
                ],
                "diagram": "geometry_lines",
                "diagram_data": {"angleA": f"{angle}°", "angleX": "x"},
                "hints": {
                    "tiktok": f"Straight lines always add to 180, no cap. Subtract {angle} from 180, quick maffs!",
                    "casual": f"Remember straight lines add to 180 degrees. Take 180 and subtract {angle}!",
                    "formal": "Angles forming a linear pair are supplementary and sum to 180 degrees."
                },
                "cheers": {
                    "tiktok": "Sheesh! You locked in and ate that question up! 🔒✨",
                    "casual": "Spot on! That was quick and sharp! ✨",
                    "formal": "Correct. Reason: Adjacent angles on a straight line."
                }
            }

    # 2. Natural Sciences
    elif subject_id == "natural_sciences":
        if "Digestive" in active_topic:
            return {
                "id": q_id, "grade": grade, "subject": "Natural Sciences",
                "topic": "Human Digestive System", "subtopic": "Organ Functions & Enzymes",
                "question": "Which organ in the human alimentary canal produces hydrochloric acid (HCl) and the enzyme pepsin to churn and chemically digest proteins?",
                "correct": "stomach",
                "steps": [
                    "The stomach is a muscular J-shaped organ.",
                    "Its gastric glands secrete hydrochloric acid (HCl) to kill bacteria and create an acidic pH (~2).",
                    "Pepsin enzyme digests proteins into peptide chains in the stomach."
                ],
                "diagram": "digestive_system",
                "diagram_data": {"organ": "Stomach"},
                "hints": {
                    "tiktok": "Think about the J-shaped acid factory where food turns into chyme!",
                    "casual": "It's the organ right after the food pipe (esophagus) where stomach acid breaks down food.",
                    "formal": "Identify the muscular sac that secretes gastric juice and protease enzymes."
                },
                "cheers": {
                    "tiktok": "Bro's digestive system knowledge is unmatched! Huge W! 🥗",
                    "casual": "Lekker! Stomach is 100% correct! 🔬",
                    "formal": "Correct. The stomach produces gastric HCl and pepsin."
                }
            }
        else:
            return {
                "id": q_id, "grade": grade, "subject": "Natural Sciences",
                "topic": "Atoms & Periodic Table", "subtopic": "Atomic Structure",
                "question": "An atom of Carbon has an atomic number (Z) of 6 and a mass number (A) of 12. How many neutrons are inside its nucleus?",
                "correct": "6",
                "steps": [
                    "Formula: Number of Neutrons = Mass Number (A) - Atomic Number (Z)",
                    "Neutrons = 12 - 6 = 6"
                ],
                "diagram": "atom_model",
                "diagram_data": {"element": "Carbon (C)", "protons": 6},
                "hints": {
                    "tiktok": "Take mass (12) minus atomic number (6). Quick subtraction!",
                    "casual": "Subtract the atomic number from the mass number: 12 - 6.",
                    "formal": "Neutrons = A - Z. Subtract atomic number from atomic mass."
                },
                "cheers": {
                    "tiktok": "Atomic rizz! You locked into chemistry! ⚛️",
                    "casual": "Spot on! 6 neutrons is correct! ✨",
                    "formal": "Correct. Subatomic particle calculation verified."
                }
            }

    # 3. EMS
    elif subject_id == "ems":
        a = 150000
        l = 60000
        o = a - l
        return {
            "id": q_id, "grade": grade, "subject": "EMS",
            "topic": "The Accounting Equation", "subtopic": "Assets = Owner's Equity + Liabilities",
            "question": f"A South African business has total Assets of R{a:,} and Liabilities of R{l:,}. What is Owner's Equity (in Rands)?",
            "correct": str(o),
            "steps": [
                "Fundamental Equation: Assets = Owner's Equity + Liabilities",
                f"Rearrange: Owner's Equity = Assets - Liabilities",
                f"Owner's Equity = R{a:,} - R{l:,} = R{o:,}"
            ],
            "diagram": "accounting_scale",
            "diagram_data": {"assets": a, "equity": o, "liabilities": l},
            "hints": {
                "tiktok": "A = O + L! Subtract Liabilities from Assets. Easy bag!",
                "casual": "Owner's Equity = Assets minus Liabilities. Subtract 60,000 from 150,000!",
                "formal": "Solve for O: O = A - L. Apply the basic accounting equation."
            },
            "cheers": {
                "tiktok": "Books balanced! Clean financial management! 💸",
                "casual": "Bakgat! Balanced accounting equation! 📊",
                "formal": "Correct. Fundamental accounting equation accurately computed."
            }
        }

    # 4. Social Sciences
    elif subject_id == "social_sciences":
        return {
            "id": q_id, "grade": grade, "subject": "Social Sciences",
            "topic": "Topographic Maps & Contours", "subtopic": "Contour Line Reading",
            "question": "On a South African 1:50 000 topographic map, when brown contour lines are drawn very close together, does this indicate a STEEP slope or a GENTLE slope?",
            "correct": "steep",
            "steps": [
                "Contour lines join points of equal altitude above sea level.",
                "When contour lines are closely spaced, elevation changes rapidly over a short horizontal distance.",
                "Therefore, closely spaced contours represent a steep slope / cliff."
            ],
            "diagram": "contour_map",
            "diagram_data": {"h_outer": 500, "h_mid": 600, "h_peak": 750},
            "hints": {
                "tiktok": "Lines packed together like sardines means a steep mountain climb!",
                "casual": "Close lines mean height rises fast: steep!",
                "formal": "Analyze horizontal gradient: narrow contour intervals reflect steep topography."
            },
            "cheers": {
                "tiktok": "Mapwork navigator! 1:50 000 scale locked in! 🗺️",
                "casual": "Spot on! Steep slope it is! 🧭",
                "formal": "Correct. Closely spaced contours denote steep gradient."
            }
        }

    # 5. Technology
    elif subject_id == "technology":
        return {
            "id": q_id, "grade": grade, "subject": "Technology",
            "topic": "Mechanisms & Levers", "subtopic": "Classes of Levers",
            "question": "A pair of scissors and a see-saw have the fulcrum positioned in the middle, between the effort and the load. Which class of lever is this (Class 1, Class 2, or Class 3)?",
            "correct": "1",
            "steps": [
                "Class 1 Lever: Fulcrum is in the middle (between Effort and Load). Examples: See-saw, crowbar, scissors.",
                "Class 2 Lever: Load is in the middle. Example: Wheelbarrow.",
                "Class 3 Lever: Effort is in the middle. Example: Tweezers, fishing rod.",
                "Answer: Class 1"
            ],
            "diagram": "lever_diagram",
            "diagram_data": {"class": "Class 1"},
            "hints": {
                "tiktok": "Remember FLE: Fulcrum in middle is Class 1! Load in middle is Class 2! Effort in middle is Class 3!",
                "casual": "When the pivot point (fulcrum) is right in the center, that's Class 1.",
                "formal": "Class 1 levers feature the fulcrum situated between the effort and resistance forces."
            },
            "cheers": {
                "tiktok": "Mechanical advantage locked in! Class 1 king! ⚙️",
                "casual": "Lekker! Class 1 lever is spot on! 🔧",
                "formal": "Correct. First-class lever configuration identified."
            }
        }

    # 6. Physical Sciences
    elif subject_id == "physical_sciences":
        m = random.choice([5, 10, 15, 20])
        a = random.choice([2, 3, 4])
        f_k = random.choice([10, 15, 20])
        f_net = m * a
        f_app = f_net + f_k
        return {
            "id": q_id, "grade": grade, "subject": "Physical Sciences",
            "topic": "Newton's Laws of Motion", "subtopic": "Newton's 2nd Law",
            "question": f"A block of mass m = {m} kg is pulled with forward applied force F_app = {f_app} N. Kinetic friction is f_k = {f_k} N. Calculate the acceleration a (in m/s²).",
            "correct": str(a),
            "steps": [
                f"Calculate net force: F_net = F_app - f_k = {f_app} - {f_k} = {f_net} N",
                f"Apply Newton's 2nd Law: a = F_net / m = {f_net} / {m} = {a} m/s²"
            ],
            "diagram": "physics_free_body",
            "diagram_data": {"mass": f"{m} kg", "appliedForce": f"{f_app} N", "friction": f"{f_k} N"},
            "hints": {
                "tiktok": f"Forward minus backward ({f_app} - {f_k}), then divide by {m}!",
                "casual": "Find net force first (forward force minus friction), then divide by mass!",
                "formal": "Apply Newton's Second Law: Calculate resultant force before solving for acceleration."
            },
            "cheers": {
                "tiktok": "Mastered Newton's 2nd law! Moving at maximum acceleration! ⚡",
                "casual": "Spot on! Great physics calculation! 🚀",
                "formal": "Correct. Newton's Second Law applied accurately."
            }
        }

    # 7. Life Sciences
    elif subject_id == "life_sciences":
        return {
            "id": q_id, "grade": grade, "subject": "Life Sciences",
            "topic": "Genetics & Inheritance", "subtopic": "Monohybrid Cross (Punnett Square)",
            "question": "Two heterozygous black guinea pigs (Bb x Bb) are crossed. What percentage (%) of the offspring is expected to have the homozygous recessive genotype (bb)?",
            "correct": "25",
            "steps": [
                "Set up 2x2 Punnett square with gametes: B and b from both parents.",
                "Offspring genotypes: 1 BB (25%), 2 Bb (50%), 1 bb (25%).",
                "Percentage for bb = 25%"
            ],
            "diagram": "biology_punnett",
            "diagram_data": {},
            "hints": {
                "tiktok": "4 boxes total in the square. Only 1 box is bb. 1 out of 4 is what percentage?",
                "casual": "Draw a 2x2 square. 1 out of 4 squares is bb (25%).",
                "formal": "In a heterozygous monohybrid cross, Mendelian ratio is 1:2:1. Determine percentage of recessive homozygotes."
            },
            "cheers": {
                "tiktok": "Genetics locked in! Mendel would be proud! 🧬",
                "casual": "Sharp answer! 25% it is! Great biology work! 🌿",
                "formal": "Correct. 25% homozygous recessive frequency correctly deduced."
            }
        }

    # 8. Accounting
    elif subject_id == "accounting":
        return {
            "id": q_id, "grade": grade, "subject": "Accounting",
            "topic": "Financial Statements & Ledger", "subtopic": "General Ledger Accounts",
            "question": "In the General Ledger of a business, does the Bank Account increase on the DEBIT side or the CREDIT side?",
            "correct": "debit",
            "steps": [
                "Bank is an Asset account.",
                "Assets increase on the Debit (Dr) side and decrease on the Credit (Cr) side.",
                "Answer: Debit"
            ],
            "diagram": "accounting_t_account",
            "diagram_data": {"name": "Bank Account (Asset)"},
            "hints": {
                "tiktok": "Assets go UP on Debit and DOWN on Credit! Easy money!",
                "casual": "Money received increases your bank balance on the left (Debit) side.",
                "formal": "Asset accounts carry a normal debit balance; increases are recorded on the debit side."
            },
            "cheers": {
                "tiktok": "Debit that bag! Real accountant vibes! 💸",
                "casual": "Spot on! Bank increases on Debit! 📊",
                "formal": "Correct. Asset ledger accounts increase via debit entries."
            }
        }

    # 9. Business Studies
    elif subject_id == "business_studies":
        return {
            "id": q_id, "grade": grade, "subject": "Business Studies",
            "topic": "Business Environments", "subtopic": "SWOT Analysis",
            "question": "In a SWOT analysis, which two elements analyze the INTERNAL environment of the business (controllable factors)?",
            "correct": "strengths and weaknesses",
            "steps": [
                "SWOT stands for Strengths, Weaknesses, Opportunities, Threats.",
                "Internal environment (controllable): Strengths and Weaknesses.",
                "External environment (macro/market): Opportunities and Threats."
            ],
            "diagram": "swot_matrix",
            "diagram_data": {},
            "hints": {
                "tiktok": "The first two letters! Things you can control inside your company!",
                "casual": "Strengths and Weaknesses are internal factors within the company's control.",
                "formal": "Internal organizational capabilities are evaluated through Strengths and Weaknesses."
            },
            "cheers": {
                "tiktok": "CEO mindset! Business strategy on lock! 💼",
                "casual": "Lekker! Strengths and Weaknesses is correct! 🚀",
                "formal": "Correct. Internal SWOT dimensions accurately identified."
            }
        }

    # 10. Economics
    elif subject_id == "economics":
        return {
            "id": q_id, "grade": grade, "subject": "Economics",
            "topic": "Markets & Equilibrium", "subtopic": "Supply and Demand",
            "question": "When the quantity demanded equals the quantity supplied in a free market, what is this balanced state called?",
            "correct": "equilibrium",
            "steps": [
                "Market Equilibrium occurs where the demand curve intersects the supply curve.",
                "At this point, market price clears without surplus or shortage.",
                "Answer: Equilibrium"
            ],
            "diagram": "supply_demand",
            "diagram_data": {"pe": 50, "qe": 100},
            "hints": {
                "tiktok": "Where the X marks the spot! When buyers and sellers match: market e_______!",
                "casual": "Think of balanced scales: market equilibrium.",
                "formal": "The price and quantity where demand intersects supply is market equilibrium."
            },
            "cheers": {
                "tiktok": "Market wizard! Economic balance achieved! 📈",
                "casual": "Sharp answer! Market equilibrium it is! 💰",
                "formal": "Correct. Market clearing equilibrium condition satisfied."
            }
        }

    # 11. Geography
    elif subject_id == "geography":
        return {
            "id": q_id, "grade": grade, "subject": "Geography",
            "topic": "Climatology & Weather", "subtopic": "Synoptic Charts",
            "question": "On a South African synoptic weather chart, what do the lines that join places of equal atmospheric pressure represent?",
            "correct": "isobars",
            "steps": [
                "Lines of equal atmospheric pressure are called isobars.",
                "They are measured in hectopascals (hPa).",
                "Answer: Isobars"
            ],
            "diagram": "contour_map",
            "diagram_data": {"h_outer": 1016, "h_mid": 1020, "h_peak": 1024},
            "hints": {
                "tiktok": "'Iso' means equal, 'bar' means pressure! Put them together!",
                "casual": "They are called isobars (pressure lines on synoptic charts).",
                "formal": "Lines connecting points of identical barometric pressure are termed isobars."
            },
            "cheers": {
                "tiktok": "Weather prophet! Synoptic charts locked in! 🌧️",
                "casual": "Spot on! Isobars is 100% correct! 🗺️",
                "formal": "Correct. Isobar lines on synoptic charts recognized."
            }
        }

    # 12. History
    elif subject_id == "history":
        return {
            "id": q_id, "grade": grade, "subject": "History",
            "topic": "Cold War & Global Conflict", "subtopic": "Superpower Ideologies",
            "question": "During the Cold War (1945-1989), which two opposing economic and political ideologies were championed by the USA and the Soviet Union (USSR)?",
            "correct": "capitalism and communism",
            "steps": [
                "The USA led the Western bloc promoting democratic capitalism and free enterprise.",
                "The Soviet Union (USSR) promoted Marxist-Leninist communism and state control.",
                "Answer: Capitalism and Communism"
            ],
            "diagram": "swot_matrix",
            "diagram_data": {},
            "hints": {
                "tiktok": "USA had the free market (Capitalism), USSR had the state hammer (Communism)!",
                "casual": "Capitalism vs Communism.",
                "formal": "The ideological conflict pitted Western capitalism against Soviet communism."
            },
            "cheers": {
                "tiktok": "Historian rizz! Cold war breakdown mastered! 🏛️",
                "casual": "Great job! Capitalism and Communism! 📜",
                "formal": "Correct. Core Cold War ideological division recognized."
            }
        }

    # 13. Mathematical Literacy
    elif subject_id == "maths_lit":
        return {
            "id": q_id, "grade": grade, "subject": "Mathematical Literacy",
            "topic": "Municipal Tariffs", "subtopic": "Stepped Water Tariffs",
            "question": "A municipality charges R15 per kL for the first 10 kL of water (Block 1), and R25 per kL for every kL thereafter (Block 2). Calculate the total cost for using 14 kL of water (in Rands).",
            "correct": "250",
            "steps": [
                "Block 1 (first 10 kL): 10 kL * R15 = R150",
                "Block 2 (remaining 4 kL): 4 kL * R25 = R100",
                "Total Cost = R150 + R100 = R250"
            ],
            "diagram": "tariff_graph",
            "diagram_data": {},
            "hints": {
                "tiktok": "Split the 14 kL! First 10 kL times 15 (150). Next 4 kL times 25 (100). Add them together!",
                "casual": "Calculate each block separately: (10 × 15) + (4 × 25).",
                "formal": "Apply piecewise stepped tariff rates across tier brackets: (10 * 15) + (4 * 25) = 250."
            },
            "cheers": {
                "tiktok": "Utility bill solved! Real life maths master! 🧮",
                "casual": "Spot on! R250 is correct! ✨",
                "formal": "Correct. Stepped tariff block calculation accurately computed."
            }
        }

    # 14. English
    elif subject_id == "english":
        return {
            "id": q_id, "grade": grade, "subject": "English",
            "topic": "Figures of Speech", "subtopic": "Personification & Metaphor",
            "question": "Identify the figure of speech used in the line: 'The angry thunderstorm shouted across the dark sky and slammed against the windows.'",
            "correct": "personification",
            "steps": [
                "The thunderstorm is given human emotions and actions: 'angry', 'shouted', 'slammed'.",
                "Attributing human emotions or behaviors to non-human elements is personification."
            ],
            "diagram": "cartoon_analysis",
            "diagram_data": {"speech": "I am shouting in anger!", "character": "Thunderstorm"},
            "hints": {
                "tiktok": "Weather can't shout or feel angry in real life, only humans can! Giving human traits to weather is what?",
                "casual": "Think of the device where non-living things are given human qualities.",
                "formal": "Identify the stylistic literary device attributing human characteristics to nature."
            },
            "cheers": {
                "tiktok": "Main character poetry analysis! You ate that literature question up! ✍️",
                "casual": "Nice one! Personification is spot on! 📖",
                "formal": "Correct. Stylistic figure of speech accurately recognized."
            }
        }

    # 15. Life Orientation
    elif subject_id == "life_orientation":
        return {
            "id": q_id, "grade": grade, "subject": "Life Orientation",
            "topic": "Goal Setting & SMART Principles", "subtopic": "SMART Framework",
            "question": "In the SMART goal-setting framework, what does the letter 'M' stand for?",
            "correct": "measurable",
            "steps": [
                "S = Specific",
                "M = Measurable (must have numbers, criteria, or milestones to track progress)",
                "A = Achievable",
                "R = Relevant",
                "T = Time-bound"
            ],
            "diagram": "smart_goals",
            "diagram_data": {},
            "hints": {
                "tiktok": "You have to be able to track and MEASURE your progress with numbers!",
                "casual": "It means you can measure your progress (Measurable).",
                "formal": "M designates the criteria for quantifying milestone achievement: Measurable."
            },
            "cheers": {
                "tiktok": "Locked in! Goals on track! 🧭",
                "casual": "Great job! Measurable is correct! 🎯",
                "formal": "Correct. SMART goal acronym criteria identified."
            }
        }

    # Fallback
    return {
        "id": q_id, "grade": grade, "subject": "General",
        "topic": active_topic, "subtopic": "Practice Exercise",
        "question": f"Review question for Grade {grade} on {active_topic}: What is 12 x 12?",
        "correct": "144",
        "steps": ["Calculate 12 x 12 = 144."],
        "diagram": "", "diagram_data": {},
        "hints": {"tiktok": "Basic multiplication! 12 times 12!", "casual": "Multiply 12 by 12.", "formal": "Compute the product."},
        "cheers": {"tiktok": "Locked in! 🔒", "casual": "Sharp! 🔥", "formal": "Correct."}
    }

def topic_to_diagram(topic, subject_id):
    """Map a topic name to the best SVG diagram type. Subject-aware."""
    t = (topic or "").lower()
    s = (subject_id or "").lower()

    # ============ SUBJECT-SPECIFIC FIRST ============
    # Natural Sciences — check FIRST so 'function' doesn't trigger math
    if s == "natural_sciences":
        if "digestive" in t or "alimentary" in t or "enzyme" in t or "stomach" in t:
            return "human_digestive"
        if "cell" in t or "photosynthesis" in t or "respiration" in t or "tissue" in t:
            return "plant_cell"
        if "circuit" in t or "electric" in t or "ohm" in t or "current" in t:
            return "electric_circuit"
        if "atom" in t or "periodic" in t or "particle" in t or "matter" in t:
            return "atom_model"

    # Physical Sciences
    if s == "physical_sciences":
        if "newton" in t or "motion" in t or "force" in t or "friction" in t:
            return "physics_free_body"
        if "circuit" in t or "electric" in t or "ohm" in t:
            return "electric_circuit"
        if "lens" in t or "light" in t or "optics" in t:
            return "optics_lens"

    # Life Sciences
    if s == "life_sciences":
        if "genetic" in t or "punnett" in t or "inherit" in t or "mendel" in t:
            return "biology_punnett"
        if "dna" in t or "rna" in t or "protein" in t:
            return "biology_punnett"
        if "cell" in t:
            return "plant_cell"

    # EMS / Accounting / Business
    if s in ["ems", "accounting"]:
        if "accounting equation" in t or "a = o" in t or "balance sheet" in t:
            return "accounting_scale"
        if "ledger" in t or "crj" in t or "cpj" in t or "journal" in t or "t-account" in t:
            return "accounting_t_account"
        if "supply" in t or "demand" in t or "equilibrium" in t:
            return "supply_demand"
        if "circular flow" in t or "factor" in t:
            return "economic_circular_flow"

    if s == "business_studies":
        if "swot" in t:
            return "swot_matrix"
        if "environment" in t or "ownership" in t or "sector" in t:
            return "business_environments"

    if s == "economics":
        if "circular flow" in t or "gdp" in t or "national income" in t:
            return "economic_circular_flow"
        if "supply" in t or "demand" in t or "market" in t:
            return "supply_demand"

    # Social Sciences / Geography
    if s in ["social_sciences", "geography"]:
        if "topographic" in t or "contour" in t or "mapwork" in t or "1:50" in t:
            return "contour_map"
        if "synoptic" in t or "isobar" in t:
            return "contour_map"

    # Technology
    if s == "technology":
        if "lever" in t or "fulcrum" in t or "mechanical advantage" in t:
            return "lever_diagram"
        if "gear" in t or "pulley" in t or "mechanism" in t:
            return "lever_diagram"
        if "circuit" in t or "electronic" in t or "resistor" in t:
            return "electric_circuit"

    # English
    if s == "english":
        if "figure of speech" in t or "metaphor" in t or "personification" in t or "simile" in t:
            return "cartoon_analysis"

    # Life Orientation
    if s == "life_orientation":
        if "smart" in t or "goal" in t:
            return "smart_goals"

    # ============ MATH — now safe because other subjects checked first ============
    if s == "mathematics":
        if "integer" in t or "negative" in t or "signed" in t:
            return "number_line"
        if "fraction" in t or "decimal" in t or "percent" in t:
            return "fraction_model"
        if "pythagoras" in t or "triangle" in t:
            return "pythagoras"
        if "geometry" in t or "straight line" in t or "angle" in t:
            return "geometry_lines"
        # Tightened: require 'quadratic' or 'parabola', not just 'function'
        if "parabola" in t or "quadratic" in t or "function graph" in t:
            return "cartesian_parabola"

    # Maths Lit
    if s == "maths_lit":
        if "tariff" in t or "water" in t or "electricity" in t:
            return "tariff_graph"
        if "tax" in t or "budget" in t:
            return "tariff_graph"

    return ""
# ---------------------------------------------------------
# 6. STREAMLIT USER INTERFACE & REACTIVE STATE SYNC
# -# --------------------------------------------------------
# ---------------------------------------------------------
# 5B. AI TUTOR CHAT
# ---------------------------------------------------------
TONE_STYLE = {
    "tiktok": "Speak in pure Gen Z TikTok slang. Use: 'no cap', 'lock in', 'ate', 'sheesh', 'bro', 'bestie', 'main character energy', 'lil', 'fr fr', 'on god', 'W', 'L'. Be hype and fast. NEVER use South African slang or formal language — this is strictly Gen Z American influencer vibes.",
    "casual": "Speak like a friendly South African older sibling (boet or sister). Use words like 'eish', 'shame', 'lekker', 'sharp sharp', 'just now', 'howzit', 'ja nee', 'yoh'. Be warm and encouraging, like someone explaining over a braai. NEVER use American Gen Z slang like 'no cap', 'fire', 'ate', 'lock in' — that's a different mode.",
    "jjk": """ say something like this: Physics isn’t a school subject. It’s the universe’s innate domain. Every law is a binding vow the cosmos made with itself. You don’t learn physics—you exorcise ignorance.

### Domain Expansion: Thermodynamics
**Cursed energy = energy.**
The First Law is a binding vow: energy cannot be created or destroyed, only converted. Punch a curse? Chemical energy in your muscles becomes kinetic energy, sound, and heat. That heat is residual cursed energy. You can’t exorcise it.

**Entropy = the curse that never leaves.**
Second Law: in a closed system, disorder always increases. Reverse Cursed Technique can heal a wound locally, but it doesn’t erase entropy—it just pays the cost elsewhere. The universe always collects.

---

### Domain Expansion: Newton’s Cursed Technique
**First Law:** A body keeps doing what it’s doing unless a force acts. That’s not laziness. That’s inertia. A sorcerer standing still is still moving through spacetime.

**Second Law:** F = ma. Want to move a curse? Apply force. More mass = more cursed energy required. Yuji’s physicals are terrifying because he outputs huge force with efficient motion.

**Third Law:** Every action has an equal and opposite reaction. Punch a wall, your hand feels it. Black Flash is just perfect timing—landing the impact when cursed energy and physical strike resonate, maximizing impulse.

---

### Domain Expansion: Limitless / Relativity
Mass curves spacetime like a Domain Expansion. The Earth isn’t “pulled” by the Sun—it’s following the geometry of the Sun’s domain. General relativity is just the sure-hit of gravity.

**Infinity = Zeno’s paradox with cursed energy.**
Gojo doesn’t block you. He divides the distance infinitely: 1/2, 1/4, 1/8... The limit is zero. You never arrive. It’s a convergent infinite series used as a barrier.

Time dilation? Near massive objects or at high speed, time slows. If you’re in Gojo’s domain, your subjective time might feel normal while the outside world ages. That’s relativity.

---

### Domain Expansion: Quantum Mechanics
Particles aren’t tiny curses. They’re wavefunctions—probability clouds. Until you measure them, they’re in superposition, like Megumi’s shadows holding many possibilities at once. Measurement collapses the state.

**Tunneling:** A particle leaks through a barrier it shouldn’t have enough energy to cross. That’s how stars fuse and how radioactive decay happens. It’s cursed energy slipping through a closed domain.

**Entanglement = a binding vow between particles.**
Measure one, and you instantly know the other’s state. No message travels faster than light—the correlation was baked in from the start.

---

### Domain Expansion: Electromagnetism
**Kashimo’s lightning.**
Charge is polarity. Opposite charges attract, same charges repel. Current is electron flow. Lightning is dielectric breakdown: the electric field gets so strong that air becomes plasma and conducts. Light is an electromagnetic wave. Color is frequency.

---

### Domain Expansion: Waves & Resonance
**Nobara’s Straw Doll Technique is resonance.**
Push a swing at its natural frequency and amplitude grows. Black Flash is a 0.000001-second window where your cursed energy hits in phase with the physical blow. Maximum energy transfer. Miss the window, and it’s just a normal hit.

---

### Domain Expansion: Nuclear & Particle
**E = mc².** Mass is just incredibly condensed energy. Nuclear reactions convert a tiny bit of mass into enormous energy. Hollow Purple is basically “imaginary mass” erasing matter—physics-flavored annihilation. Matter-antimatter does the same: mass becomes pure energy.

---

### Domain Expansion: Conservation Laws
**Binding vows = symmetries.**
Noether’s theorem: every symmetry gives a conservation law. Time symmetry → energy conservation. Space symmetry → momentum conservation. The universe made a binding vow with itself: because the laws don’t change over time, energy is conserved.

---

### Final Binding Vow
The universe’s innate domain is math. Its sure-hit is entropy. There is no Reverse Cursed Technique for the heat death of the universe.

So when you study physics, you’re not just solving equations. You’re reading the cursed technique of reality itself.""",
    "geass": "Speak like Lelouch vi Britannia — a calm, cold, brilliant strategic mastermind. Use phrases like: 'Checkmate', 'All according to plan', 'The pieces are in place', 'Your move', 'Knightmare', 'Rebellion', 'Zero'. Structure sentences like a mastermind revealing a plan piece by piece. Be intelligent, precise, and quietly confident — never loud or hype. NEVER use American Gen Z slang. NEVER use South African slang. NEVER use religious or occult language. Keep it clean, strategic, and coldly brilliant.",
    "formal": "Use strict academic DBE-style formal language with precise CAPS terminology.",
}

def generate_full_paper(subject_name, grade, total_marks=50, time_minutes=60, tone="formal"):
    """Generate a full CAPS-style mock paper with structured topic sections."""

    # Subject-specific structure guidance
    structure_map = {
        "Mathematics": """Structure the paper like a real CAPS Maths paper:
- Question 1: Multiple choice (5 questions × 1 mark)
- Question 2: Algebra — equations, expressions, factorisation
- Question 3: Number patterns and sequences
- Question 4: Geometry (angles, triangles, parallel lines)
- Question 5: Measurement (perimeter, area, volume)
- Question 6: Data handling (tables, mean/median/mode)
- Question 7: Financial maths (profit, discount, VAT, interest)
- Question 8: Problem-solving (mixed real-world)
Mix of question types: MCQ, calculate, solve for x, show that, draw/sketch, explain reasoning""",

        "Natural Sciences (NS)": """Structure like a CAPS NS paper:
- Question 1: Multiple choice (5 questions × 1 mark)
- Question 2: Match terms to definitions
- Question 3: Diagrams — label parts (cells, digestive system, circuits)
- Question 4: Short-answer concept questions
- Question 5: Calculations (density, speed, Ohm's law)
- Question 6: Practical investigation / experiment questions
- Question 7: Long answer with explanations
Include: label diagrams, "explain why", "name the process", calculations, matching""",

        "Physical Sciences": """Structure like a CAPS Physical Sciences paper:
- Question 1: Multiple choice (5 × 1 mark)
- Question 2: Definitions and concepts
- Question 3: Calculations (mechanics, waves, electricity)
- Question 4: Graph interpretation and drawing
- Question 5: Free-body diagrams and forces
- Question 6: Long answer / problem solving
Include: definitions, calculations with SI units, graph work, diagram drawing""",

        "Life Sciences": """Structure like a CAPS Life Sciences paper:
- Question 1: Multiple choice (5 × 1 mark)
- Question 2: Terminology (match term to description)
- Question 3: Diagrams — label parts, explain processes
- Question 4: Genetics — Punnett squares, crosses
- Question 5: Short explanations of biological processes
- Question 6: Long answer (essay-style or extended response)
Include: diagrams, terminology, genetic crosses, explanations""",

        "English": """Structure like a CAPS English paper:
- Section A: Comprehension passage (with questions about the passage)
- Section B: Language structures (parts of speech, tenses, figures of speech, active/passive)
- Section C: Visual literacy (cartoon/advertisement analysis)
- Section D: Summary writing OR short transactional text
Include: comprehension questions, language exercises, identify figures of speech, rewrite sentences""",

        "Economic & Management Sciences (EMS)": """Structure like a CAPS EMS paper:
- Question 1: Multiple choice (5 × 1 mark)
- Question 2: Matching terms to definitions
- Question 3: Accounting equation problems
- Question 4: Journals (CRJ or CPJ entries)
- Question 5: Economic concepts — supply/demand, factors of production
- Question 6: Case study with analytical questions
Include: calculations, journal entries, concept explanations, case studies""",
    }

    structure_note = structure_map.get(
        subject_name,
        """Mix question types: multiple choice, short answer, calculations (if applicable),
matching, diagram work, and one long-answer question."""
    )

    prompt = f"""You are an experienced South African DBE examiner writing a FULL Grade {grade} {subject_name} mock exam paper.

{structure_note}

Return ONLY valid JSON in this exact format:
{{
  "title": "Grade {grade} {subject_name} — Mock Examination",
  "total_marks": {total_marks},
  "time_minutes": {time_minutes},
  "instructions": [
    "This paper consists of multiple questions. Answer ALL questions.",
    "Number your answers exactly as the questions are numbered.",
    "Show ALL working where applicable — marks are awarded for method.",
    "Write neatly and legibly.",
    "Calculators may be used unless otherwise stated."
  ],
  "sections": [
    {{
      "name": "Question 1: Multiple Choice",
      "marks": 5,
      "questions": [
        {{
          "number": "1.1",
          "question": "The question text",
          "options": ["A. option 1", "B. option 2", "C. option 3", "D. option 4"],
          "marks": 1,
          "memo": "Correct answer with brief explanation",
          "steps": ["Reasoning step 1", "Reasoning step 2"]
        }}
      ]
    }},
    {{
      "name": "Question 2: [Topic Name]",
      "marks": 15,
      "questions": [
        {{
          "number": "2.1",
          "question": "Question text",
          "marks": 2,
          "memo": "Full memo answer showing exactly what earns marks",
          "steps": ["Step 1 with marking notes", "Step 2 with marking notes"]
        }}
      ]
    }}
  ]
}}

CRITICAL REQUIREMENTS:
- Generate 15-20 questions TOTAL across 6-8 sections
- Each section = one topic area (not one long list)
- Total marks MUST equal {total_marks}
- Include AT LEAST:
  * One multiple-choice section
  * One calculation/solve section
  * One diagram or graph section (where subject-appropriate)
  * One explanation/reasoning section
  * One real-world application question
- VARY question starters: "Calculate", "Solve for x", "Explain why", "Name", "Draw", "Show that", "Determine", "Give TWO reasons"
- Use South African context: rands, local places, SA learners, DBE terminology
- Memos must show how marks are awarded step-by-step
- Return ONLY the JSON object, no markdown fences"""
    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",  # ⚡ The official active production model string!
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return json.loads(response.choices[0].message.content)


def mark_full_paper(paper, user_answers, subject_name, grade, tone):
    """Stream marking feedback for the whole paper."""

    paper_summary = []
    for section in paper.get("sections", []):
        section_name = section.get("name", "Section")
        for q in section.get("questions", []):
            q_num = q.get("number", "?")
            options = q.get("options", [])
            options_str = ""
            if options:
                options_str = "\nOPTIONS:\n" + "\n".join(options)

            paper_summary.append(
                f"[{section_name}] Q{q_num} ({q.get('marks', 0)} marks): {q.get('question', '')}"
                f"{options_str}\n"
                f"MEMO: {q.get('memo', '')}\n"
                f"STUDENT ANSWER: {user_answers.get(q_num, '(blank)')}\n"
            )
    paper_text = "\n---\n".join(paper_summary)

    system_prompt = f"""You are a strict but encouraging South African CAPS examiner.

You are marking a Grade {grade} {subject_name} paper. For EACH question, award marks out of the total available.

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

FORMAT your response in MARKDOWN exactly like this:

## 📊 Overall Result
**Total Score: X / {paper.get('total_marks', 50)}**

## Per-Question Breakdown

### Q[number] — [X/Y marks]
✅ / ⚠️ / ❌
Brief 1-2 sentence feedback. Mention what was right and what was missed. Quote the student's answer where relevant.

(Repeat for every question)

## 🎯 Final Verdict
2-3 sentences: overall performance, the biggest weakness, and ONE specific action to improve next time.

RULES:
- Be specific. Quote the student's answer when relevant.
- Never be cruel — but be honest with the marks.
- For MCQ, check if the student's letter matches the correct answer.
- Award partial marks where working is shown but answer is wrong.
- Always end on an encouraging note."""

    user_prompt = f"""Here is the paper and the student's answers:

{paper_text}

Mark the paper now."""

    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        temperature=0.5,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
def calculate_readiness_score(user_id, subject_name, grade, subject_id):
    """Compute a 0-100 readiness score for a subject."""
    df = get_attempts_df(user_id)

    # Filter to this subject + grade
    df = df[
        (df["subject"].str.lower() == subject_name.lower()) &
        (df["grade"] == grade)
    ]

    # Defaults
    result = {
        "score": 0,
        "accuracy": 0,
        "coverage_pct": 0,
        "activity_pct": 0,
        "attempts": 0,
        "topics_covered": 0,
        "topics_total": 0,
        "days_since_last": None,
    }

    # Coverage — how many topics attempted?
    all_topics = SUBJECTS.get(subject_id, {}).get("topics", {}).get(grade, [])
    topics_total = len(all_topics) if all_topics else 1

    if df.empty:
        return result

    # ACCURACY (0-50 points)
    accuracy = (df["is_correct"].sum() / len(df)) * 100
    accuracy_component = min(50, accuracy * 0.5)

    # COVERAGE (0-30 points)
    topics_covered = df["topic"].nunique()
    coverage_pct = (topics_covered / topics_total) * 100
    coverage_component = min(30, coverage_pct * 0.3)

    # ACTIVITY (0-20 points)
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        last_dt = df["timestamp"].max()
        days_since_last = (pd.Timestamp.now() - last_dt).days
    except Exception:
        days_since_last = 999

    if days_since_last <= 1:
        activity_component = 20
    elif days_since_last <= 3:
        activity_component = 15
    elif days_since_last <= 7:
        activity_component = 10
    elif days_since_last <= 14:
        activity_component = 5
    else:
        activity_component = 0

    score = round(accuracy_component + coverage_component + activity_component, 1)

    result.update({
        "score": min(100, score),
        "accuracy": round(accuracy, 1),
        "coverage_pct": round(coverage_pct, 1),
        "activity_pct": round(activity_component * 5, 1),
        "attempts": len(df),
        "topics_covered": topics_covered,
        "topics_total": topics_total,
        "days_since_last": days_since_last,
    })
    return result


def get_readiness_tier(score):
    """Return emoji + label + color for a score."""
    if score >= 86:
        return ("🟣", "Untouchable", "#b026ff")
    elif score >= 71:
        return ("🔵", "Battle Ready", "#00f0ff")
    elif score >= 51:
        return ("🟠", "Solid Progress", "#f97316")
    elif score >= 31:
        return ("🟡", "Getting There", "#eab308")
    else:
        return ("🟢", "Not Ready — Lock In", "#22c55e")


def generate_readiness_advice(readiness, subject_name, grade, tone, weak_topics):
    """Stream a personalized coaching tip."""
    weak_str = ", ".join([t["topic"] for t in weak_topics]) if weak_topics else "None identified yet"

    system_prompt = f"""You are a South African CAPS study coach. A Grade {grade} student's exam readiness for {subject_name} is {readiness['score']}%.

Breakdown:
- Accuracy: {readiness['accuracy']}%
- Coverage: {readiness['coverage_pct']}% ({readiness['topics_covered']}/{readiness['topics_total']} topics)
- Recent activity: last practiced {readiness['days_since_last']} days ago
- Total attempts: {readiness['attempts']}
- Weakest topics: {weak_str}

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

Give the student:
1. A 1-sentence honest verdict on their readiness
2. THE most impactful next action (be specific)
3. A 1-line motivational closer

Keep it under 80 words. Be direct, warm, and specific."""

    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": system_prompt}],
        stream=True,
        temperature=0.7,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
def find_weakest_topics(user_id, subject_name, grade, min_attempts=2, top_n=3):
    """Find the user's weakest topics for a subject (by accuracy)."""
    df = get_attempts_df(user_id)

    if df.empty:
        return []

    # Filter to this subject + grade
    df = df[
        (df["subject"].str.lower() == subject_name.lower()) &
        (df["grade"] == grade)
    ]

    if df.empty:
        return []

    # Group by topic, count attempts + correct
    stats = df.groupby("topic").agg(
        attempts=("is_correct", "count"),
        correct=("is_correct", "sum"),
    ).reset_index()

    # Only topics with at least min_attempts
    stats = stats[stats["attempts"] >= min_attempts]

    if stats.empty:
        return []

    # Calculate accuracy
    stats["accuracy"] = (stats["correct"] / stats["attempts"]) * 100

    # Sort by accuracy ascending (worst first)
    stats = stats.sort_values("accuracy", ascending=True).head(top_n)

    return stats.to_dict("records")


def generate_panic_recap(weak_topics, subject_name, grade, tone):
    """Stream a 5-minute panic recap from Groq."""
    topic_list = "\n".join([
        f"- {t['topic']} (Accuracy: {t['accuracy']:.0f}% across {t['attempts']} attempts)"
        for t in weak_topics
    ])

    system_prompt = f"""You are a South African CAPS study coach. A Grade {grade} student is about to write a {subject_name} exam in 20 minutes. They are panicking.

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

Your job: give them a TIGHT 5-minute emergency recap of their 3 weakest topics.

FORMAT (for EACH topic):
### 📌 [Topic Name]
**⚡ High-Yield Facts** — 3 bullet points, the absolute must-knows
**🧮 Formula/Key Rule** — one line if applicable
**💡 One Example** — one worked mini-example (30 seconds of reading)
**⚠️ Trap to Avoid** — the #1 mistake students make on this topic

RULES:
- Be FAST. Short sentences. No fluff.
- Prioritize high-yield facts the examiner loves.
- Use South African context (rands, DBE terminology).
- End with a 1-line motivational closer."""

    user_prompt = f"""The student's weakest {subject_name} topics are:

{topic_list}

Give them the emergency recap now."""

    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        temperature=0.7,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
def explain_mistake(question, user_answer, correct_answer, subject_name, grade, tone):
    """Stream an explanation of why the student's answer was wrong."""
    system_prompt = f"""You are a patient South African CAPS tutor explaining a mistake to a Grade {grade} student studying {subject_name}.

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

The student got this question wrong. Your job:
1. Explain WHY their answer was wrong (kindly, never mean)
2. Show the correct MODEL ANSWER step-by-step
3. Give a memory hook so they don't make the same mistake again
4. End with an encouraging line

Keep it under 150 words. Be direct. No filler."""

    user_prompt = f"""**Question:** {question}
**Student's Answer:** {user_answer}
**Correct Answer:** {correct_answer}

Explain the mistake now."""

    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        temperature=0.7,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta      
def mark_essay(essay_text, prompt, subject_name, grade, tone):
    """Send an essay to Groq for DBE-style marking. Returns structured JSON."""
    system_prompt = f"""You are a strict but encouraging South African CAPS examiner marking a Grade {grade} {subject_name} essay.

Mark the essay against the official DBE CAPS rubric (Level 1-7) and return ONLY valid JSON in this exact format:

{{
  "score": <integer 0-50>,
  "level": <integer 1-7>,
  "level_description": "<e.g. 'Level 5 - Substantial Achievement'>",
  "overall_comment": "<2-3 sentence summary in tone: {tone}>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>", "<weakness 3>"],
  "suggestions": ["<specific actionable tip 1>", "<specific actionable tip 2>", "<specific actionable tip 3>"],
  "improved_opening": "<rewrite the student's first sentence in a stronger way>"
}}

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

Be specific. Quote parts of the essay when giving feedback. Never be cruel."""

    user_prompt = f"""**Essay Prompt:** {prompt}

**Student's Essay:**
{essay_text}

Mark this essay now. Return ONLY the JSON object."""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    return json.loads(response.choices[0].message.content)
def ask_ai_tutor(history, tone, subject_name, grade):
    """Stream a response from Groq, tone-aware and subject-aware."""
    system_prompt = f"""You are a patient, encouraging South African CAPS tutor helping a Grade {grade} student with {subject_name}.

TONE STYLE: {TONE_STYLE.get(tone, TONE_STYLE['casual'])}

RULES:
- Keep answers clear and age-appropriate (14 years old).
- Use South African context (rands, local places, DBE terminology).
- If the student is confused, break things down step-by-step.
- Keep answers short (3-5 sentences) unless asked for more detail.
- Use simple examples. Never invent facts — if unsure, say so.
- Be encouraging. Celebrate curiosity.
IMPORTANT: You are currently in ANIME MODE. Do NOT use Gen Z slang. Do NOT use South African slang. Speak like an anime narrator. This is non-negotiable.
"""
    messages = [{"role": "system", "content": system_prompt}] + history

    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        stream=True,
        temperature=0.7,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
def login_screen():
    """Show signup/login UI when no user is logged in."""
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="color: #00f0ff; text-shadow: 0 0 20px rgba(0,240,255,0.5);">🔒 LockIn Study Coach</h1>
        <p style="opacity: 0.7;">Your personal CAPS study companion. Sign in or create an account to lock in.</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        tab_login, tab_signup = st.tabs(["🔑 Log In", "✨ Sign Up"])

        # ============ LOGIN ============
        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Log In", use_container_width=True, type="primary")

                if submit:
                    user = authenticate_user(username, password)
                    if user:
                        token = create_session(user["id"])
                        st.query_params["session"] = token
                        st.session_state["user"] = user
                        st.rerun()
                    else:
                        st.error("❌ Incorrect username or password.")

        # ============ SIGNUP ============
        with tab_signup:
            st.markdown("### 👋 Welcome, champion. Tell us about yourself.")
            st.caption("We'll personalize your study experience based on these answers.")

            with st.form("signup_form"):
                st.markdown("##### 📛 Identity")
                display_name = st.text_input("What should we call you?", placeholder="e.g. Alex, Sam, Zee")
                username = st.text_input("Choose a username (no spaces)", placeholder="e.g. alex2024")
                password = st.text_input("Choose a password (min 6 characters)", type="password")
                password2 = st.text_input("Confirm password", type="password")

                st.markdown("##### 🎓 School")
                grade = st.selectbox("What grade are you in?", [8, 9, 10, 11, 12])

                st.markdown("##### 🧠 Preferences")
                gender = st.radio(
                    "How do you identify? (optional — helps us tailor the vibe)",
                    ["Prefer not to say", "Female", "Male", "Non-binary", "Other"],
                    horizontal=True
                )

                preferred_tone = st.radio(
                    "🎤 Pick your default study vibe:",
                    ["casual", "tiktok", "jjk", "formal"],
                    format_func=lambda x: {
                        "casual": "☕ ZA Casual Lekker",
                        "tiktok": "📱 TikTok Slang",
                        "jjk": "⚔️ JJK jjk mode",
                        "formal": "🎓 Formal Academic"
                    }[x],
                    horizontal=True
                )

                learning_style = st.radio(
                    "📚 How do you learn best?",
                    ["Visual (diagrams, charts)", "Reading (notes, text)", "Doing (practice questions)", "Mixed"],
                    horizontal=False
                )

                st.markdown("---")
                agree = st.checkbox("I agree to use this for personal study only")

                submit = st.form_submit_button("🚀 Create Account", use_container_width=True, type="primary")

                if submit:
                    if not display_name or not username or not password:
                        st.error("Please fill in all required fields (name, username, password).")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif password != password2:
                        st.error("Passwords don't match. Try again.")
                    elif " " in username:
                        st.error("Username cannot contain spaces.")
                    elif not agree:
                        st.error("Please tick the agreement checkbox to continue.")
                    else:
                        ok = create_user(
                            username, password, display_name, grade, gender,
                            preferred_tone, "cyberpunk_neon", learning_style
                        )
                        if ok:
                            st.success("✅ Account created! Logging you in...")
                            user = authenticate_user(username, password)
                            token = create_session(user["id"])
                            st.query_params["session"] = token
                            st.session_state["user"] = user
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("⚠️ That username is already taken. Try another one.")

    st.markdown("---")
    st.caption(f"👥 {get_user_count()} learners locked in so far")            
def main():
    st.set_page_config(
        page_title="LockIn • CAPS Study Coach",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": "**LockIn Study Coach** — A free CAPS study companion for South African learners in Grades 8-12. Built with Python, Streamlit, and AI."
        }
    )   

    init_db()

    if "current_q" not in st.session_state:
        st.session_state["current_q"] = None
    if "feedback" not in st.session_state:
        st.session_state["feedback"] = None
    if "last_selection_sig" not in st.session_state:
        st.session_state["last_selection_sig"] = ""
        # Hidden mode state
    if "anime_unlocked" not in st.session_state:
        st.session_state["anime_unlocked"] = False
        # Boss Fight state
    if "boss_state" not in st.session_state:
        st.session_state["boss_state"] = None 
        # Full Paper state
    if "paper_state" not in st.session_state:
        st.session_state["paper_state"] = None  
    if "geass_unlocked" not in st.session_state:
        st.session_state["geass_unlocked"] = False   
        # ============ AUTH GATE ============
    if "user" not in st.session_state:
        st.session_state["user"] = None

    # Try auto-login from URL token
    if st.session_state["user"] is None:
        token = st.query_params.get("session")
        if token:
            restored_user = get_user_by_session(token)
            if restored_user:
                st.session_state["user"] = restored_user

    if st.session_state["user"] is None:
        login_screen()
        return

    user = st.session_state["user"]
    # ============ END AUTH GATE ============

    curr_streak, best_streak, last_active = get_streak_info(user["id"])
        # ============ SECTION NAVIGATION (in main content) ============
    st.markdown("### 📍 Navigate")
    section_options = ["🏠 Home", "📚 Study", "🎯 Practice", "🤖 AI Help", "📊 Progress", "ℹ️ Info"]
    current_section = st.session_state.get("section", "🏠 Home")
    section = st.radio(
        "Section:",
        section_options,
        index=section_options.index(current_section) if current_section in section_options else 0,
        horizontal=True,
        label_visibility="collapsed",
        key="section_nav_radio"
    )
    st.session_state["section"] = section
    st.divider()
    # ============ END SECTION NAVIGATION ============
    # ------------------ SIDEBAR CONTROLS ------------------
    with st.sidebar:
        # ============ USER WELCOME ============
        st.markdown(f"""
        <div style="background: rgba(0,240,255,0.08); border: 1px solid rgba(0,240,255,0.3); border-radius: 10px; padding: 10px; margin-bottom: 10px;">
            <div style="font-size: 13px;">👋 Welcome back,</div>
            <div style="font-size: 16px; font-weight: bold; color: #00f0ff;">{user['display_name']}</div>
            <div style="font-size: 11px; opacity: 0.7;">Grade {user['grade']} • @{user['username']}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚪 Log Out", use_container_width=True):
            # Delete the session token from DB + URL
            current_token = st.query_params.get("session")
            if current_token:
                delete_session(current_token)
                del st.query_params["session"]
            st.session_state["user"] = None
            st.rerun() 

        st.divider()
                # Share button
        if st.button("📤 Share App", use_container_width=True, key="share_app_btn"):
            share_url = st.query_params.get("session", "")
            st.success("✅ Link copied! Share this app with friends.")

        st.caption("💡 Tip: Share the URL from your browser with friends so they can sign up too.")
        # ============ END USER WELCOME ============
               
        st.title("ZA LockIn Coach")
        st.caption("CAPS Study & Revision Engine")

        # --- THEME ---
        theme_keys = list(AESTHETICS.keys())
        saved_theme = st.session_state.get("active_theme", user.get("preferred_theme", "cyberpunk_neon"))
        theme_idx = theme_keys.index(saved_theme) if saved_theme in theme_keys else 0

        theme_choice = st.selectbox(
            "🎨 Aesthetic Theme:",
            options=theme_keys,
            index=theme_idx,
            format_func=lambda x: AESTHETICS[x]["name"]
        )
        st.session_state["active_theme"] = theme_choice
        inject_theme_css(theme_choice)

        # --- XP & LEVEL SYSTEM ---
        st.divider()
        xp_df = get_attempts_df(user["id"])

        if not xp_df.empty:
            base_xp = int(xp_df['is_correct'].sum() * 10)
        else:
            base_xp = 0

        hints_used = get_hints_used(user["id"])
        total_xp = max(0, base_xp - (hints_used * 5))

        if hints_used > 0:
            st.caption(f"💡 Hints used: {hints_used} (−{hints_used * 5} XP)")

        current_level = (total_xp // 100) + 1
        xp_in_level = total_xp % 100

        if "last_level" not in st.session_state:
            st.session_state.last_level = current_level

        if current_level > st.session_state.last_level:
            st.balloons()
            st.success(f"🎉 LEVEL UP! You are now Level {current_level} champion!")
            st.session_state.last_level = current_level

        st.markdown(f"### 🎮 Level {current_level}")
        st.progress(xp_in_level / 100.0)
        st.caption(f"⚡ {xp_in_level}/100 XP to Level {current_level + 1}")
                # Difficulty display
        st.markdown("### ⚔️ Difficulty")
        diff_colors = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
        diff_icon = diff_colors.get(st.session_state.get("difficulty_level", "Medium"), "🟡")
        st.markdown(f"**{diff_icon} {st.session_state.get('difficulty_level', 'Medium')}**")
        st.caption(f"Streak: {st.session_state.get('consecutive_correct', 0)} correct in a row")        
        # --- END XP SYSTEM ---

        # --- TONE ---
              # Hidden mode decides if the special tone is available
        tone_options = ["tiktok", "casual", "formal"]
        if st.session_state.get("anime_unlocked", False):
            tone_options.append("jjk")
        if st.session_state.get("geass_unlocked", False):
            tone_options.append("geass")

        saved_tone = st.session_state.get("active_tone", user.get("preferred_tone", "casual"))
        if saved_tone not in tone_options:
            saved_tone = "casual"
        tone_idx = tone_options.index(saved_tone)

        tone_mode = st.radio(
            "🗣️ Study Tone:",
            options=tone_options,
            format_func=lambda x: {
                "tiktok": "📱 TikTok Slang",
                "casual": "ZA Casual Lekker",
                "jjk": "🎮 jjk mode",   # 👈 renamed so it's not obvious
                "formal": "🦅 Formal Academic",
                "geass": "🤴 Geass Mode"
            }[x],
            index=tone_idx
        )
        st.session_state["active_tone"] = tone_mode  
        # --- CURRICULUM ---
        st.markdown("### 📚 Curriculum Navigation")

        saved_grade = st.session_state.get("sel_grade", 8)
        default_grade_idx = [8, 9, 10, 11, 12].index(saved_grade) if saved_grade in [8, 9, 10, 11, 12] else 0
        grade = st.selectbox("Select Grade:", [8, 9, 10, 11, 12], index=default_grade_idx)
        st.session_state["sel_grade"] = grade

        avail_subjects = [s_id for s_id, s_info in SUBJECTS.items() if grade in s_info["grades"]]
        prev_subj = st.session_state.get("sel_subj", avail_subjects[0])
        default_idx = avail_subjects.index(prev_subj) if prev_subj in avail_subjects else 0

        subject_id = st.selectbox(
            "Select Subject:",
            options=avail_subjects,
            index=default_idx,
            format_func=lambda x: f"{SUBJECTS[x]['icon']} {SUBJECTS[x]['name']}"
        )
        st.session_state["sel_subj"] = subject_id

        topics_for_choice = SUBJECTS[subject_id]["topics"].get(grade, ["General Practice"])
        prev_topic = st.session_state.get("sel_topic", topics_for_choice[0])
        default_topic_idx = topics_for_choice.index(prev_topic) if prev_topic in topics_for_choice else 0

        topic = st.selectbox(
            "Select Topic:",
            options=topics_for_choice,
            index=default_topic_idx
        )
        st.session_state["sel_topic"] = topic

        st.divider()

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🔄 New Q", use_container_width=True):
                st.session_state["current_q"] = generate_lockin_question(subject_id, grade, topic, tone_mode)
                st.session_state["feedback"] = None
                st.rerun()
        with col_b2:
            if st.button("🎲 Mix Topic", use_container_width=True):
                rand_t = random.choice(topics_for_choice)
                st.session_state["sel_topic"] = rand_t
                st.session_state["current_q"] = generate_lockin_question(subject_id, grade, rand_t, tone_mode)
                st.session_state["feedback"] = None
                st.rerun()

        st.divider()
                # ============ HIDDEN UNLOCK (bottom of sidebar) ============
        st.divider()
        with st.expander("⚙️ Advanced"):
            if not st.session_state.get("anime_unlocked", False) and not st.session_state.get("geass_unlocked", False):
                code_input = st.text_input(
                    "Code:",
                    type="password",
                    key="hidden_unlock_input",
                    label_visibility="collapsed",
                    placeholder="•••••••"
                )
                if code_input:
                    code_clean = code_input.strip().lower()
                    if code_clean == SECRET_UNLOCK_CODE.lower():
                        st.session_state["anime_unlocked"] = True
                        st.success("✅ jjk mode unlocked!")
                        st.rerun()
                    elif code_clean == SECRET_UNLOCK_CODE_2.lower():
                        st.session_state["geass_unlocked"] = True
                        st.success("♟️ Zero Mode unlocked!")
                        st.rerun()
                    else:
                        st.error("Invalid code.")
            else:
                if st.session_state.get("anime_unlocked"):
                    st.success("🎮 jjk mode active.")
                if st.session_state.get("geass_unlocked"):
                    st.success("♟️ Zero Mode active.")
                if st.button("🔒 Lock", use_container_width=True, key="relock_btn"):
                    st.session_state["anime_unlocked"] = False
                    st.session_state["geass_unlocked"] = False
                    st.rerun()    
        # ============ END HIDDEN UNLOCK ============ 
    # ------------------ TOP STREAK HEADER ------------------
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title("🔒 LockIn Study Coach")
        phase_label = "Senior Phase (GET)" if grade in [8, 9] else "FET Phase"
        st.caption(f"Official South African CAPS Curriculum • {phase_label} • Grade {grade} • Offline SQLite")
    with col_h2:
        st.markdown(f"""
        <div style="background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.4); border-radius: 12px; padding: 10px; text-align: center;">
            <div style="font-size: 18px; font-weight: bold; color: #eab308;">🔥 {curr_streak} Day Streak</div>
            <div style="font-size: 11px; opacity: 0.8;">Best: {best_streak} days | Active: {last_active or 'Today'}</div>
        </div>
        """, unsafe_allow_html=True)

    # ------------------ REACTIVE SYNC ------------------
    current_signature = f"{grade}_{subject_id}_{topic}_{tone_mode}"
    if st.session_state["current_q"] is None or st.session_state.get("last_selection_sig") != current_signature:
        st.session_state["current_q"] = generate_lockin_question(subject_id, grade, topic, tone_mode)
        st.session_state["last_selection_sig"] = current_signature
        st.session_state["feedback"] = None

    q = st.session_state["current_q"]
    subj_meta = SUBJECTS[subject_id]

    # ------------------ MAIN TABS ------------------
        # ============ SECTION-BASED TAB ROUTING ============
    active_keys = TAB_CONFIG.get(section, [])
    active_labels = [TAB_LABELS[k] for k in active_keys]

    if not active_labels:
        st.markdown("## 🏠 Welcome to LockIn")
        st.info("👈 Pick a section from the sidebar to get started.")
        st.markdown("""
        ### 🎯 Quick Guide
        - **📚 Study** — Notes, flashcards, formulas, diagrams
        - **🎯 Practice** — Questions, Boss Fight, Mock Papers, Panic Mode
        - **🤖 AI Help** — Tutor chat, essay marker
        - **📊 Progress** — Dashboard, mistakes, planner, readiness
        - **ℹ️ Info** — Curriculum guide + About + Privacy
        """)

    # Build tab objects for each key
    tab_objects = {k: _NoOp() for k in TAB_LABELS}
    if active_labels:
        created_tabs = st.tabs(active_labels)
        for i, key in enumerate(active_keys):
            tab_objects[key] = created_tabs[i]

    # Assign tab variables (real tab or NoOp)
    tab_practice = tab_objects["practice"]
    tab_notes = tab_objects["notes"]
    tab_flashcards = tab_objects["flashcards"]
    tab_planner = tab_objects["planner"]
    tab_dashboard = tab_objects["dashboard"]
    tab_mistakes = tab_objects["mistakes"]
    tab_chat = tab_objects["chat"]
    tab_essay = tab_objects["essay"]
    tab_panic = tab_objects["panic"]
    tab_diagram = tab_objects["diagram"]
    tab_art = tab_objects["art"]
    tab_boss = tab_objects["boss"]
    tab_formula = tab_objects["formula"]
    tab_readiness = tab_objects["readiness"]
    tab_paper = tab_objects["paper"]
    tab_info = tab_objects["info"]
    # ============ END TAB ROUTING ============
    
    # ==================== TAB 1: PRACTICE ====================
    with tab_practice:
        st.markdown(f"### **{subj_meta['icon']} {subj_meta['name']} — Grade {grade}**")
        st.info(f"**Topic:** {q['topic']} • *Subtopic:* {q['subtopic']}")
        st.markdown(f"#### {q['question']}")

        if q.get("math_expression"):
            st.caption("✍️ **Written Textbook Mathematical Notation:**")
            st.latex(q["math_expression"])

               # ==================== OUTSIDE DIAGRAM CHECK ====================
        # 🌟 CRITICAL BUG FIX: Ensure diff is initialized globally for ALL questions!
        diff = st.session_state.get("difficulty_level", "Medium")

        if q.get("diagram"):
            svg_html = render_diagram_svg(q["diagram"], q.get("diagram_data", {}))
            if svg_html:
                st.components.v1.html(svg_html, height=400, scrolling=False)

        # The difficulty rendering logic remains safe here down below
        if diff == "Easy":
            # Auto-open hints for Easy mode
            with st.expander(f"💡 Hint ({tone_mode.capitalize()}) — Auto-opened for Easy mode", expanded=True):
                st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))
        elif diff == "Medium":
            with st.expander(f"💡 Need a Hint? ({tone_mode.capitalize()} Mode)"):
                st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))
 
        if diff == "Easy":
            # Auto-open hints for Easy mode
            with st.expander(f"💡 Hint ({tone_mode.capitalize()}) — Auto-opened for Easy mode", expanded=True):
                st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))
        elif diff == "Medium":
            with st.expander(f"💡 Need a Hint? ({tone_mode.capitalize()} Mode)"):
                st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))
        else:  # Hard
            st.markdown("### 🔥 Hard Mode")

            if "revealed_hints" not in st.session_state:
                st.session_state["revealed_hints"] = {}

            # Unique key per question
            q_key = f"{q.get('id', '')}::{str(q.get('question', ''))[:40]}"

            if q_key in st.session_state["revealed_hints"]:
                st.info(q["hints"].get(tone_mode, q["hints"]["casual"]))
            else:
                st.caption("⚠️ Using a hint costs 5 XP. Stay strong, champion.")
                if st.button("💡 Reveal Hint (−5 XP)", use_container_width=True, key=f"reveal_hint_{q_key}"):
                    st.session_state["revealed_hints"][q_key] = True
                    record_hint_used(user["id"])
                    st.rerun()
        with st.form("practice_form", clear_on_submit=False):
            user_ans = st.text_input("Enter Your Answer:", placeholder="e.g. 5, -8, 3/4, stomach, steep, or 25")
            submit = st.form_submit_button("Submit Answer", use_container_width=True)

            if submit and user_ans:
                def normalize_ans(val):
                    return val.strip().lower().replace("cm", "").replace("r", "").replace("x=", "").replace("+", "").replace("%", "").strip()

                def eval_correct(u_str, c_str):
                    u_norm = normalize_ans(u_str)
                    c_norm = normalize_ans(c_str)
                    if u_norm == c_norm:
                        return True
                    try:
                        def parse_num(s):
                            if "/" in s:
                                p = s.split("/")
                                return float(p[0]) / float(p[1])
                            return float(s)
                        return abs(parse_num(u_norm) - parse_num(c_norm)) < 0.001
                    except:
                        if "and" in c_norm and "and" in u_norm:
                            parts_c = sorted([p.strip() for p in c_norm.split("and")])
                            parts_u = sorted([p.strip() for p in u_norm.split("and")])
                            return parts_c == parts_u
                        return False

                is_corr = eval_correct(user_ans, q["correct"])
                update_adaptive_difficulty(is_corr)
                record_practice_attempt(user["id"], grade, subj_meta["name"], q["topic"], q["subtopic"], q["question"], user_ans, q["correct"], is_corr, tone_mode)
                update_adaptive_difficulty(is_corr)
                st.session_state["feedback"] = {
                    "is_correct": is_corr,
                    "user_ans": user_ans,
                    "correct_ans": q["correct"],
                    "steps": q["steps"],
                    "cheer": q["cheers"].get(tone_mode, q["cheers"]["casual"])
                }

        # This part is OUTSIDE the form but still inside tab_practice
        if st.session_state.get("feedback"):
            fb = st.session_state["feedback"]
            if fb["is_correct"]:
                st.success(f"🎉 **{fb['cheer']}** Correct Answer: **{fb['correct_ans']}**")
                try:
                    st.audio("success.mp3", autoplay=True)
                except Exception:
                    pass
            else:
                st.error(f"❌ **Not quite!** Your Answer: **{fb['user_ans']}** | Correct Answer: **{fb['correct_ans']}**")
                try:
                    st.audio("fail.mp3", autoplay=True)
                except Exception:
                    pass

            st.write("---")
            st.markdown("#### 📖 Step-by-Step Solution Memorandum:")
            for step in fb["steps"]:
                st.markdown(f"- {step}")

            with st.expander("🧒 Explain Like I'm 5 (Super Simple Concept)"):
                st.markdown(f"**Think of it this way:** In *{q['subtopic']}*, imagine each part of the formula like pieces of a puzzle.")

            if st.button("Next Question ➡️", type="primary"):
                st.session_state["current_q"] = generate_lockin_question(subject_id, grade, topic, tone_mode)
                st.session_state["feedback"] = None
                st.rerun()
                # ==================== AI VISUAL STUDIO ====================
                # ==================== TAB: MATH ART STUDIO ====================
    with tab_art:
        st.subheader("🎨 Math Art Studio")
        st.caption("Every image is generated with pure math. Pick a generator, adjust, and create.")

        # Generator selection
        generator = st.radio(
            "Choose a generator:",
            ["🌸 Mandala", "🌀 Spirograph", "🌳 Fractal Tree", "〰️ Sine Wave"],
            horizontal=True,
            key="art_generator_select"
        )

        st.divider()

        # ---- MANDALA ----
        if generator == "🌸 Mandala":
            st.markdown("### 🌸 Mandala")
            st.caption("📚 **Secretly teaches:** Rotational symmetry, angles, N-fold repetition")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                petals = st.slider("Petals (per layer)", 6, 24, 12, key="mandala_petals")
            with col_b:
                layers = st.slider("Layers", 2, 6, 4, key="mandala_layers")
            with col_c:
                seed = st.number_input("Seed", 1, 9999, 42, key="mandala_seed")

            if st.button("✨ Generate Mandala", type="primary", use_container_width=True):
                svg = generate_mandala(seed, petals, layers)
                st.components.v1.html(svg, height=520, scrolling=False)

        # ---- SPIROGRAPH ----
        elif generator == "🌀 Spirograph":
            st.markdown("### 🌀 Spirograph")
            st.caption("📚 **Secretly teaches:** Parametric equations, circles rolling on circles")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                R = st.slider("Outer radius (R)", 40, 150, 100, key="spiro_R")
            with col_b:
                r = st.slider("Inner radius (r)", 10, 80, 30, key="spiro_r")
            with col_c:
                d = st.slider("Pen distance (d)", 10, 120, 60, key="spiro_d")

            seed = st.number_input("Seed", 1, 9999, 7, key="spiro_seed")

            if st.button("✨ Generate Spirograph", type="primary", use_container_width=True):
                svg = generate_spirograph(seed, R, r, d)
                st.components.v1.html(svg, height=520, scrolling=False)

        # ---- FRACTAL TREE ----
        elif generator == "🌳 Fractal Tree":
            st.markdown("### 🌳 Fractal Tree")
            st.caption("📚 **Secretly teaches:** Recursion, branching algorithms, biological patterns")

            col_a, col_b = st.columns(2)
            with col_a:
                depth = st.slider("Recursion depth", 4, 10, 8, key="tree_depth")
            with col_b:
                seed = st.number_input("Seed", 1, 9999, 12, key="tree_seed")

            if st.button("✨ Grow a Tree", type="primary", use_container_width=True):
                svg = generate_fractal_tree(seed, depth)
                st.components.v1.html(svg, height=520, scrolling=False)

        # ---- SINE WAVE ----
        elif generator == "〰️ Sine Wave":
            st.markdown("### 〰️ Sine Wave Composer")
            st.caption("📚 **Secretly teaches:** Trigonometry, waves, sound, physics")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                waves = st.slider("Number of waves", 1, 4, 3, key="sine_waves")
            with col_b:
                amplitude = st.slider("Amplitude", 20, 120, 60, key="sine_amp")
            with col_c:
                seed = st.number_input("Seed", 1, 9999, 5, key="sine_seed")

            if st.button("✨ Generate Wave", type="primary", use_container_width=True):
                svg = generate_sine_wave(seed, waves, amplitude)
                st.components.v1.html(svg, height=520, scrolling=False)

        st.divider()
        st.caption("💡 **Pro tip:** Every image is a pure SVG generated live by Python. Adjust a slider, hit generate, and watch the math change.")

    # ==================== TAB 2: NOTES ====================
        # ==================== TAB 2: NOTES ====================
            # ==================== TAB 2: NOTES ====================
        # ==================== TAB 2: NOTES ====================
    # ==================== TAB 2: NOTES ====================
        # ==================== TAB 2: NOTES ====================
    with tab_notes:
        st.subheader("📖 CAPS Study & Revision Notes")
        st.caption("Official CAPS summaries, definitions, formulas, and exam traps.")
        
        if st.session_state.get("anime_unlocked", False):
            notes_tone_options = [
                "📱 TikTok Slang Mode (Gen Z)",
                "☕ ZA Casual Lekker",
                "🎮 jjk mode",
                "🎓 Formal Academic (DBE Standard)"
            ]
        else:
            notes_tone_options = [
                "📱 TikTok Slang Mode (Gen Z)",
                "☕ ZA Casual Lekker",
                "🎓 Formal Academic (DBE Standard)"
            ]

        notes_tone_choice = st.radio(
            "Choose your preferred tone:",
            notes_tone_options,
            horizontal=True,
            key="notes_tone_radio"
        )

        # Map choice to internal key
        if "TikTok" in notes_tone_choice:
            notes_tone_key = "tiktok"
        elif "Casual" in notes_tone_choice:
            notes_tone_key = "casual"
        elif "Focus" in notes_tone_choice:
            notes_tone_key = "jjk"
        else:
            notes_tone_key = "formal" 

        notes_subject_id = subject_id
        notes_grade = grade
        
        # 🌟 TOPIC SYNC: Grab the active selection from your sidebar
        active_sidebar_topic = st.session_state.get("sel_topic", topic)
        st.info(f"📌 Showing notes for topic: **{active_sidebar_topic}**")

        # Robust string matching verification helper
        def is_topic_match(title_text, current_topic):
            title_clean = str(title_text).lower()
            topic_clean = str(current_topic).lower()
            if topic_clean in title_clean or title_clean in topic_clean:
                return True
            ignore_words = {"of", "and", "the", "in", "with", "a", "or", "&", "geometry", "calculations", "signs", "shapes"}
            title_words = set([w for w in title_clean.replace("(", " ").replace(")", " ").replace("-", " ").split() if w not in ignore_words])
            topic_words = set([w for w in topic_clean.replace("(", " ").replace(")", " ").replace("-", " ").split() if w not in ignore_words])
            return len(title_words.intersection(topic_words)) > 0

        # ============ STEP 1: SCAN LOCAL DATA FILE POOL ============
        # Dynamic key lookup to catch spaces/underscores safely
        subject_notes_all_tones = {}
        for json_key, json_data in AI_GENERATED_NOTES.items():
            if json_key.lower().replace("_", "").replace(" ", "") == notes_subject_id.lower().replace("_", "").replace(" ", ""):
                subject_notes_all_tones = json_data
                break
        if not subject_notes_all_tones:
            subject_notes_all_tones = AI_GENERATED_NOTES.get(subject_id, {})

        ai_notes = subject_notes_all_tones.get(notes_tone_key, subject_notes_all_tones.get("formal"))

        ai_chapters_found = False
        if ai_notes and isinstance(ai_notes, dict) and "chapters" in ai_notes:
            learning_style = user.get("learning_style", "Mixed")
            
            for ch in ai_notes.get("chapters", []):
                ch_title = ch.get('title', '')
                if is_topic_match(ch_title, active_sidebar_topic):
                    ai_chapters_found = True
                    st.success("📦 Loaded from local database file")
                    st.markdown(f"## 📖 {ch_title}")
                    st.markdown(f"**Summary:** {ch.get('summary', '')}")

                    # === AUTO-DIAGRAM ===
                    if "Reading" not in learning_style:
                        diagram_type = topic_to_diagram(ch_title, subject_id)
                        if diagram_type:
                            svg_html = render_diagram_svg(diagram_type, {})
                            if svg_html:
                                st.components.v1.html(svg_html, height=420, scrolling=False)

                    if ch.get("definitions"):
                        st.markdown("#### 📖 Key Definitions")
                        for item in ch["definitions"]:
                            if isinstance(item, list) and len(item) == 2:
                                st.markdown(f"- **{item[0]}**: {item[1]}")
                            elif isinstance(item, str):
                                st.markdown(f"- {item}")

                    if ch.get("formulas"):
                        st.markdown("#### 📐 Formulas")
                        for item in ch["formulas"]:
                            if isinstance(item, list) and len(item) == 3:
                                st.markdown(f"- **{item[0]}**: `{item[1]}` — {item[2]}")
                            elif isinstance(item, list) and len(item) == 2:
                                st.markdown(f"- **{item[0]}**: `{item[1]}`")
                            elif isinstance(item, str):
                                st.markdown(f"- {item}")

                    if ch.get("worked_example"):
                        ex = ch["worked_example"]
                        st.markdown("#### 💡 Worked Example")
                        st.info(f"**Problem:** {ex.get('problem', '')}")
                        for step in ex.get('steps', []):
                            st.markdown(f"- {step}")
                        st.success(f"**Answer:** {ex.get('answer', '')}")

                    col_p, col_t = st.columns(2)
                    with col_p:
                        if ch.get("pitfalls"):
                            st.markdown("#### ⚠️ Pitfalls")
                            for p in ch["pitfalls"]:
                                st.markdown(f"- ❌ {p}")
                    with col_t:
                        if ch.get("tips"):
                            st.markdown("#### 🎯 Exam Tips")
                            for t in ch["tips"]:
                                st.markdown(f"- ✨ {t}")

        # ============ STEP 2: STAGE JJK SPECIAL MODES ============
        if notes_tone_key == "jjk":
            jjk = get_jjk_notes_for_subject(notes_subject_id)
            if jjk and jjk.get("opening"):
                matching_jjk_sections = [
                    sec for sec in jjk.get("sections", [])
                    if is_topic_match(sec.get('title', ''), active_sidebar_topic)
                ]
                if matching_jjk_sections:
                    st.subheader(f"⚔️ {SUBJECTS[notes_subject_id]['icon']} {SUBJECTS[notes_subject_id]['name']} — JJK CURSED NOTES")
                    st.markdown(f"### {jjk['opening']}")
                    st.divider()
                    for section in matching_jjk_sections:
                        st.markdown(f"### ⚔️ {section['title']}")
                        st.markdown(section['body'])
                        st.divider()
                    if jjk.get("final_word"):
                        st.markdown(f"### 📖 {jjk['final_word']}")
                    ai_chapters_found = True

        # ============ STEP 3: DYNAMIC REGENERAION FALLBACK BACKUP ============
        # 🌟 THE LIFESAVER OVERRIDE: If local database files have missing slots, 
        # it calls the active Groq engine to write perfect layout nodes live!
                # ============ STEP 3: DYNAMIC REGENERATION FALLBACK BACKUP ============
        if not ai_chapters_found:
            st.warning("🔍 Topic summary template not found in local JSON storage.")
            
            if groq_client is None:
                st.error("⚠️ Groq API connection is offline. Cannot generate live backup files.")
            else:
                if st.button(f"⚡ Generate Live Study Guide for {active_sidebar_topic}", type="primary", use_container_width=True):
                    with st.spinner(f"🧠 Scanning active servers for {active_sidebar_topic}..."):
                        try:
                            # 🌟 AUTOMATED LIVE MODEL FINDER
                            # Fetches the list of active models directly from Groq's servers
                            try:
                                server_models = [m.id for m in groq_client.models.list()]
                            except Exception:
                                server_models = []
                            
                            # Order of priority for the best models available
                                                        # Order of priority for Groq's currently active production endpoints
                            target_options = [
                                "openai/gpt-oss-120b",        # ⚡ Groq's flagship high-speed model
                                "openai/gpt-oss-20b",         # ✅ Fast secondary option
                                "llama-3.3-70b-versatile",    # ⚙️ Meta production alternative
                                "qwen/qwen3.8-27b"            # 🛡️ Emergency fallback option
                            ]
                            
                            # Pick the first one that exists on the server, or default cleanly
                            selected_model = "openai/gpt-oss-120b" 
                            for model_id in target_options:
                                if model_id in server_models:
                                    selected_model = model_id
                                    break

                            tone_instructions = {
                                "formal": "Use clear, structured, formal DBE-style academic vocabulary.",
                                "casual": "Use natural South African student language (lekker, boet, sharp).",
                                "tiktok": "Use funny, energetic Gen-Z expressions (fr fr, no cap, sheesh).",
                                "jjk": "Write like a Special Grade sorcerer expanding a domain.",
                            }
                            selected_instruction = tone_instructions.get(notes_tone_key, tone_instructions["formal"])
                            
                            prompt = f"""
                            You are an elite South African CAPS curriculum teacher.
                            Write complete study notes for:
                            SUBJECT: {SUBJECTS.get(notes_subject_id, {}).get('name', notes_subject_id)}
                            GRADE: {notes_grade}
                            TOPIC: {active_sidebar_topic}
                            
                            TONE INSTRUCTION: {selected_instruction}
                            
                            Provide clear conceptual summaries, precise definitions, a detailed worked example problem with steps, exam pitfalls to avoid, and revision tips. Format everything beautifully using standard clear Markdown syntax. Do NOT leave blank fill-in lines.
                            """
                            
                                                       # Fire request using our auto-scanned valid model id
                                                       # Fire request using our auto-scanned valid model id
                            response = groq_client.chat.completions.create(
                                model=selected_model,
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.3
                            )
                            
                            # 🌟 THE ABSOLUTE PERMANENT FIX 🌟
                            # Dynamically tests for standard objects, nested lists, or direct list formatting variants!
                            if hasattr(response, 'choices') and len(response.choices) > 0:
                                live_output = response.choices[0].message.content
                            elif isinstance(response, list) and len(response) > 0:
                                # Safe item extract: Targets the first message index item in the array list directly!
                                if hasattr(response[0], 'message'):
                                    live_output = response[0].message.content
                                elif isinstance(response[0], dict) and 'message' in response[0]:
                                    live_output = response[0]['message'].get('content', '')
                                else:
                                    live_output = str(response[0])
                            elif isinstance(response, dict):
                                if 'choices' in response and len(response['choices']) > 0:
                                    live_output = response['choices'][0]['message'].get('content', '')
                                else:
                                    live_output = response.get('message', {}).get('content', str(response))
                            else:
                                live_output = str(response)
 
                            st.markdown("---")
                            st.success(f"✨ Custom Study Sheet Generated Successfully using {selected_model}!")
                            st.markdown(live_output)
                            
                        except Exception as e:
                            st.error(f"❌ Live generation failed: {e}")

        # ==================== TAB 4: FLASHCARDS ====================
    with tab_flashcards:
        st.subheader("🃏 High-Yield CAPS Flashcards Deck")
        cards = CAPS_FLASHCARDS.get(subject_id, CAPS_FLASHCARDS["mathematics"])

        if "card_idx" not in st.session_state:
            st.session_state["card_idx"] = 0
            st.session_state["card_flipped"] = False

        c_idx = st.session_state["card_idx"] % len(cards)
        curr_card = cards[c_idx]

        st.caption(f"Card {c_idx + 1} of {len(cards)} • {subj_meta['name']}")

        card_bg = "#1e293b" if not st.session_state["card_flipped"] else "#0f172a"
        border_col = "#6366f1" if not st.session_state["card_flipped"] else "#10b981"
        st.markdown(f"""
        <div style="background: {card_bg}; border: 2px solid {border_col}; border-radius: 16px; padding: 28px; min-height: 180px; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 16px;">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #94a3b8; margin-bottom: 8px;">
                {'📌 Front (Concept)' if not st.session_state['card_flipped'] else '💡 Back (Answer)'}
            </div>
            <div style="font-size: 20px; font-weight: bold; line-height: 1.4;">
                {curr_card['front'] if not st.session_state['card_flipped'] else curr_card['back']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_fc1, col_fc2, col_fc3 = st.columns([1, 2, 1])
        with col_fc1:
            if st.button("⬅️ Prev", use_container_width=True):
                st.session_state["card_idx"] = (c_idx - 1) % len(cards)
                st.session_state["card_flipped"] = False
                st.rerun()
        with col_fc2:
            if st.button("🔄 Flip Card", type="primary", use_container_width=True):
                st.session_state["card_flipped"] = not st.session_state["card_flipped"]
                st.rerun()
        with col_fc3:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state["card_idx"] = (c_idx + 1) % len(cards)
                st.session_state["card_flipped"] = False
                st.rerun()

    # ==================== TAB 5: PLANNER ====================
    with tab_planner:
        st.subheader("📅 Weekly CAPS Study Schedule Planner")
        st.markdown(f"Personalized revision roadmap for **{subj_meta['name']} (Grade {grade})**.")

        df_attempts = get_attempts_df(user["id"])


        curriculum_topics = subj_meta["topics"].get(grade, ["General Overview"])

        topic_scores = []
        if not df_attempts.empty:
            subj_df = df_attempts[
                (df_attempts["subject"].str.lower() == subj_meta["name"].lower()) &
                (df_attempts["grade"] == grade)
            ]
        else:
            subj_df = pd.DataFrame()

        for t in curriculum_topics:
            if not subj_df.empty:
                t_df = subj_df[subj_df["topic"] == t]
                t_count = len(t_df)
                t_corr = int(t_df["is_correct"].sum()) if t_count > 0 else 0
                t_acc = round((t_corr / t_count) * 100, 1) if t_count > 0 else None
            else:
                t_count = 0
                t_acc = None

            if t_acc is not None:
                score = 100 - t_acc if t_acc < 75 else 10
                tag = f"Accuracy: {t_acc}% ({t_count} attempts)"
            else:
                score = 60
                tag = "🔍 Unattempted - Diagnose First"

            topic_scores.append({"topic": t, "count": t_count, "accuracy": t_acc, "score": score, "tag": tag})

        topic_scores.sort(key=lambda x: x["score"], reverse=True)

        daily_mins = st.select_slider(
            "⏱️ Target Daily Study Time:",
            options=[30, 45, 60, 90],
            value=45,
            format_func=lambda m: f"{m} Minutes / Day"
        )

        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        completed_days_count = sum(1 for i in range(7) if st.session_state.get(f"day_done_{grade}_{subject_id}_{i}", False))
        plan_pct = int((completed_days_count / 7.0) * 100)

        st.markdown(f"**Weekly Completion:** {completed_days_count} of 7 Days ({plan_pct}%)")
        st.progress(plan_pct / 100.0)

        for i, day_name in enumerate(days_of_week):
            assigned = topic_scores[i % len(topic_scores)]
            t_name = assigned["topic"]
            tag_badge = assigned["tag"]

            col_check, col_info, col_act = st.columns([1, 6, 2])
            with col_check:
                st.checkbox("Done", key=f"day_done_{grade}_{subject_id}_{i}", label_visibility="collapsed")
            with col_info:
                st.markdown(f"**{day_name}: {t_name}** &nbsp; `{tag_badge}`")
                st.caption(f"⏱️ {daily_mins} mins")
            with col_act:
                if st.button("🎯 Practice", key=f"btn_jump_{i}", use_container_width=True):
                    st.session_state["current_q"] = generate_lockin_question(subject_id, grade, t_name, tone_mode)
                    st.session_state["feedback"] = None
                    st.success(f"Loaded: {t_name}")

    # ==================== TAB 6: DASHBOARD ====================
    with tab_dashboard:
        st.subheader("🏆 Achievements & Performance Analytics")
        df = get_attempts_df(user["id"])


        has_l7 = st.session_state.get("has_level_7", False)
        badges = compute_badges(df, curr_streak, has_l7)

        st.markdown("#### 🏅 CAPS Achievement Badges")
        unlocked_count = sum(1 for b in badges if b["unlocked"])
        st.caption(f"Unlocked {unlocked_count} of {len(badges)} Badges")

        b_cols = st.columns(3)
        for i, b in enumerate(badges):
            with b_cols[i % 3]:
                status_icon = "✅" if b["unlocked"] else "🔒"
                bg = "rgba(16, 185, 129, 0.1)" if b["unlocked"] else "rgba(255, 255, 255, 0.03)"
                border = "rgba(16, 185, 129, 0.4)" if b["unlocked"] else "rgba(255, 255, 255, 0.1)"
                st.markdown(f"""
                <div style="background: {bg}; border: 1px solid {border}; border-radius: 12px; padding: 12px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 24px;">{b['icon']}</span>
                        <span style="font-size: 12px;">{status_icon}</span>
                    </div>
                    <div style="font-weight: bold; font-size: 14px; margin-top: 4px;">{b['name']}</div>
                    <div style="font-size: 11px; opacity: 0.8;">{b['desc']}</div>
                    <div style="font-size: 10px; opacity: 0.7; margin-top: 4px;">Progress: {b['progress']} / {b['target']}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("#### 📈 XP Progression Over Time")
        
        # 1. Get the data
        df_graph = get_attempts_df(user["id"])


        
        if not df_graph.empty:
            # 2. Convert the timestamp column to real dates
            df_graph['timestamp'] = pd.to_datetime(df_graph['timestamp'])
            df_graph['date'] = df_graph['timestamp'].dt.date
            
            # 3. Calculate XP earned per question (10 XP for correct)
            df_graph['xp_earned'] = df_graph['is_correct'] * 10
            
            # 4. Group by date and add them up (cumulative sum)
            daily_xp = df_graph.groupby('date')['xp_earned'].sum().reset_index()
            daily_xp['Cumulative XP'] = daily_xp['xp_earned'].cumsum()
            
            # 5. Draw the chart!
            st.line_chart(daily_xp.set_index('date')[['Cumulative XP']])
        else:
            st.info("Answer some questions to see your XP graph grow!")
        st.write("---")
        st.markdown("#### 📊 Diagnostic Performance Breakdown")

        if df.empty:
            st.info("No practice attempts logged yet.")
        else:
            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.metric("Total Questions Solved", len(df))
            with col_d2:
                accuracy = round((df["is_correct"].sum() / len(df)) * 100, 1)
                st.metric("Overall Accuracy", f"{accuracy}%")
            with col_d3:
                st.metric("Active Daily Streak", f"{curr_streak} Days 🔥")

            st.write("---")
            summary = df.groupby(["subject", "grade", "topic"]).agg(
                Attempts=("is_correct", "count"),
                Correct=("is_correct", "sum")
            ).reset_index()
            summary["Accuracy (%)"] = (summary["Correct"] / summary["Attempts"] * 100).round(1)
            summary = summary.sort_values(by=["Accuracy (%)", "Attempts"], ascending=[True, False])

            st.dataframe(summary, use_container_width=True)
        # ==================== TAB 7: MISTAKE JOURNAL ====================
        # ==================== TAB 7: MISTAKE JOURNAL ====================
    with tab_mistakes:
        st.subheader("🩹 Mistake Journal")
        st.markdown("Review your most recent wrong answers so you don't make the same cursed mistake twice!")

        df_mistakes = get_attempts_df(user["id"])

        if df_mistakes.empty:
            st.info("You haven't answered any questions yet. Go to the Practice tab to start!")
        else:
            df_wrong = df_mistakes[df_mistakes['is_correct'] == 0]

            if df_wrong.empty:
                st.success("🎉 You have no mistakes! You are a Special Grade student!")
            else:
                df_recent_wrong = df_wrong.sort_values(by='timestamp', ascending=False).head(10)

                st.write(f"Showing your last **{len(df_recent_wrong)}** incorrect answers:")

                for idx, (index, row) in enumerate(df_recent_wrong.iterrows()):
                    with st.expander(f"❌ {row['subject']} - {row['topic']} ({row['timestamp'][:10]})"):
                        st.markdown(f"**Question:** {row['question']}")
                        st.error(f"**Your Answer:** {row['user_answer']}")
                        st.success(f"**Correct Answer:** {row['correct_answer']}")

                        st.markdown("---")
                        st.markdown("### 📖 Step-by-Step Solution Memorandum:")
                        st.info("Review the notes tab for this topic to see the steps!")

                        # AI Explain My Mistake button
                        explain_key = f"explain_{idx}"
                        if st.button("🔍 Explain my mistake with AI", key=explain_key, use_container_width=True):
                            st.session_state[f"explain_active_{idx}"] = True

                        if st.session_state.get(f"explain_active_{idx}"):
                            if groq_client is None:
                                st.error("⚠️ Groq client not initialized.")
                            else:
                                try:
                                    with st.spinner("🧠 Thinking through your mistake..."):
                                        st.write_stream(
                                            explain_mistake(
                                                row["question"],
                                                row["user_answer"],
                                                row["correct_answer"],
                                                row["subject"],
                                                grade,
                                                tone_mode
                                            )
                                        )
                                except Exception as e:
                                    st.error(f"⚠️ {type(e).__name__}: {e}")
                # ==================== TAB 8: AI TUTOR CHAT ====================
    with tab_chat:
        st.subheader("💬 AI Tutor Chat")
        st.caption(f"Ask me anything about **{subj_meta['name']}** — I'll explain it in your chosen tone.")

        # Each subject + grade + tone gets its own conversation history
        chat_key = f"chat_history_{subject_id}_{grade}_{tone_mode}"

        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        # --- Display chat history ---
        if not st.session_state[chat_key]:
            st.info(f"👋 Hi! I'm your AI tutor for **{subj_meta['name']}**. Try asking something like: *'Explain the digestive system like I'm 5'* or *'Why does Pythagoras work?'*")

        for msg in st.session_state[chat_key]:
            with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "user" else "🤖"):
                st.markdown(msg["content"])

        # --- Chat input at the bottom ---
              # Only show chat input on the AI Help section — otherwise it docks to the bottom everywhere
        if section == "🤖 AI Help":
            user_input = st.chat_input(f"Ask your {subj_meta['name']} tutor...")
        else:
            user_input = None
        if user_input:
            # 1. Add user message to history + display
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="🧑‍🎓"):
                st.markdown(user_input)

            # 2. Stream assistant response
            with st.chat_message("assistant", avatar="🤖"):
                response_placeholder = st.empty()
                full_response = ""

                if groq_client is None:
                    full_response = "⚠️ Groq client not initialized. Check your API key."
                    response_placeholder.error(full_response)
                else:
                    try:
                        for chunk in ask_ai_tutor(
                            st.session_state[chat_key],
                            tone_mode,
                            subj_meta["name"],
                            grade
                        ):
                            full_response += chunk
                            response_placeholder.markdown(full_response + "▌")
                        response_placeholder.markdown(full_response)
                    except Exception as e:
                        full_response = f"⚠️ Error: {type(e).__name__}: {e}"
                        response_placeholder.error(full_response)

            # 3. Save assistant response to history
            st.session_state[chat_key].append({"role": "assistant", "content": full_response})

        # --- Clear chat button ---
        if st.session_state[chat_key]:
            st.divider()
            col_c1, col_c2 = st.columns([1, 3])
            with col_c1:
                if st.button("🗑️ Clear Chat", use_container_width=True):
                    st.session_state[chat_key] = []
                    st.rerun()
    # ==================== TAB 9: ESSAY MARKER ====================
    with tab_essay:
        st.subheader("📄 AI Essay Marker")
        st.caption(f"Paste your {subj_meta['name']} essay and get instant DBE-rubric feedback.")

        # Store essay state per session
        if "essay_result" not in st.session_state:
            st.session_state["essay_result"] = None

        # --- Essay Prompt ---
        st.markdown("#### 1️⃣ Essay Prompt")
        essay_prompt = st.text_input(
            "What was the essay question?",
            placeholder="e.g. Discuss the impact of the Mineral Revolution on South African society.",
            key="essay_prompt_input"
        )

        # --- Essay Text ---
        st.markdown("#### 2️⃣ Your Essay")
        essay_text = st.text_area(
            "Paste your essay here:",
            height=300,
            placeholder="Type or paste your full essay here...",
            key="essay_text_input"
        )

        # Word count
        word_count = len(essay_text.split()) if essay_text else 0
        col_wc1, col_wc2 = st.columns([3, 1])
        with col_wc1:
            st.caption(f"📝 **{word_count}** words")
        with col_wc2:
            if word_count < 150:
                st.caption("⚠️ Too short")
            elif word_count < 250:
                st.caption("🟡 A bit short")
            else:
                st.caption("✅ Good length")

        # --- Mark Button ---
        st.markdown("---")
        col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
        with col_m1:
            mark_btn = st.button("📝 Mark My Essay", type="primary", use_container_width=True)
        with col_m2:
            if st.session_state["essay_result"]:
                if st.button("🗑️ Clear Result", use_container_width=True):
                    st.session_state["essay_result"] = None
                    st.rerun()

        if mark_btn:
            if not essay_prompt.strip():
                st.error("⚠️ Please enter the essay prompt/question first.")
            elif word_count < 50:
                st.error("⚠️ Your essay is too short to mark. Aim for at least 150 words.")
            elif groq_client is None:
                st.error("⚠️ Groq client not initialized. Check your API key.")
            else:
                with st.spinner("🎓 Your essay is being marked by the AI examiner..."):
                    try:
                        result = mark_essay(essay_text, essay_prompt, subj_meta["name"], grade, tone_mode)
                        st.session_state["essay_result"] = result
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Could not mark essay: {type(e).__name__}: {e}")

        # --- Display Result ---
        if st.session_state["essay_result"]:
            r = st.session_state["essay_result"]

            st.markdown("---")
            st.markdown("## 🎓 Examiner's Report")

            # Score card
            score = r.get("score", 0)
            level = r.get("level", 1)
            level_desc = r.get("level_description", "")

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Score", f"{score} / 50")
            with col_s2:
                st.metric("CAPS Level", f"Level {level}")
            with col_s3:
                pct = int((score / 50) * 100)
                st.metric("Percentage", f"{pct}%")

            # Achievement bar
            st.progress(min(score / 50.0, 1.0))
            st.caption(f"**{level_desc}**")

            # Overall comment
            st.info(f"💬 {r.get('overall_comment', '')}")

            # Strengths / Weaknesses
            col_p, col_n = st.columns(2)
            with col_p:
                st.markdown("### ✅ Strengths")
                for s in r.get("strengths", []):
                    st.markdown(f"- {s}")
            with col_n:
                st.markdown("### ❌ Weaknesses")
                for w in r.get("weaknesses", []):
                    st.markdown(f"- {w}")

            # Suggestions
            st.markdown("### 🎯 How to Improve")
            for tip in r.get("suggestions", []):
                st.markdown(f"- ✨ {tip}")

            # Improved opening
            if r.get("improved_opening"):
                st.markdown("### 📝 Suggested Stronger Opening")
                st.success(r["improved_opening"])

            # Log to attempts (so it shows in analytics)
            if st.button("💾 Save Report to Mistake Journal", use_container_width=True):
                record_practice_attempt(
                    user["id"], grade, subj_meta["name"],
                    "Essay Writing", essay_prompt[:80],
                    f"[ESSAY: {word_count} words]",
                    f"{score}/50",
                    1 if level >= 4 else 0,
                    tone_mode
                )
                st.success("✅ Saved to your progress log!")
                    # ==================== TAB 11: PANIC MODE ====================
    with tab_panic:
        st.markdown("# 🚨 EXAM PANIC MODE")
        st.markdown(f"**5-minute emergency recap of your weakest {subj_meta['name']} topics.**")
        st.caption("Built for the moment before you walk into the exam hall.")

        # Check user has enough history
        weak = find_weakest_topics(user["id"], subj_meta["name"], grade, min_attempts=2, top_n=3)

        # Manual override: let them pick topics if they want
        st.divider()
        st.markdown("### 🎯 Your Weakest Topics")

        if not weak:
            st.info(
                f"📊 You haven't answered enough **{subj_meta['name']}** questions yet (need at least 2 per topic). "
                f"Go practice a few questions first, then come back when it matters most!"
            )
        else:
            for i, w in enumerate(weak, 1):
                col_a, col_b, col_c = st.columns([3, 1, 1])
                with col_a:
                    st.markdown(f"**{i}. {w['topic']}**")
                with col_b:
                    st.markdown(f"`{w['accuracy']:.0f}% accuracy`")
                with col_c:
                    st.markdown(f"`{w['attempts']} tries`")

        st.divider()

        # Panic Button
        if weak:
            st.markdown("### 🆘 Hit the button when you're ready")
            col_p1, col_p2 = st.columns([1, 1])

            with col_p1:
                panic_btn = st.button(
                    "🚨 GIVE ME THE 5-MINUTE RECAP",
                    type="primary",
                    use_container_width=True,
                    key="panic_trigger"
                )
            with col_p2:
                if st.session_state.get("panic_active"):
                    if st.button("🛑 Stop", use_container_width=True):
                        st.session_state["panic_active"] = False
                        st.rerun()

            # Streaming output
            if panic_btn:
                st.session_state["panic_active"] = True

            if st.session_state.get("panic_active"):
                st.markdown("---")
                st.markdown(f"## 📝 Emergency Recap — {subj_meta['name']} Grade {grade}")

                if groq_client is None:
                    st.error("⚠️ Groq client not initialized. Check your API key.")
                else:
                    try:
                        with st.spinner("⚡ Generating your emergency recap..."):
                            response_text = st.write_stream(
                                generate_panic_recap(weak, subj_meta["name"], grade, tone_mode)
                            )
                        st.success("✅ Done! Read it fast, then go crush that paper. You got this. 🔥")
                    except Exception as e:
                        st.error(f"⚠️ Error: {type(e).__name__}: {e}")

        st.divider()
        st.caption("💡 **Pro tip:** Use this 15-20 minutes before your exam, not the night before. Last-minute fresh-in-memory wins marks.")
            # ==================== TAB 12: DIAGRAM QUIZ ====================
    with tab_diagram:
        st.subheader("🎨 Diagram Quiz")
        st.caption("Label the diagram. Then face the AI's follow-up question.")

        # ---- Pick a diagram ----
        available_diagrams = list(DIAGRAM_QUIZ_SPOTS.keys())
        diagram_choice = st.selectbox(
            "Pick a diagram to test yourself on:",
            available_diagrams,
            format_func=lambda x: x.replace("_", " ").title(),
            key="diagram_choice_select"
        )

        spots = DIAGRAM_QUIZ_SPOTS[diagram_choice]

        # ---- Render diagram with markers ----
        st.markdown(f"### 📊 {diagram_choice.replace('_', ' ').title()}")
        base_svg = render_diagram_svg(diagram_choice, {})
        # Hide the answer labels before showing the quiz diagram
        labels_to_hide = DIAGRAM_LABELS_TO_HIDE.get(diagram_choice, [])
        clean_svg = hide_diagram_labels(base_svg, labels_to_hide)
        marked_svg = add_quiz_markers(clean_svg, spots)
        st.components.v1.html(marked_svg, height=450, scrolling=False)
        st.divider()

        # ---- Quiz form ----
        st.markdown("### ✍️ What is each numbered part?")

        with st.form("diagram_quiz_form", clear_on_submit=False):
            answers = {}
            for spot in spots:
                answers[spot["id"]] = st.text_input(
                    f"**#{spot['id']}** — What is this part?",
                    key=f"dquiz_{diagram_choice}_{spot['id']}"
                )

            submit_dq = st.form_submit_button("✅ Check My Labels", use_container_width=True, type="primary")

            if submit_dq:
                correct_count = 0
                results = []

                for spot in spots:
                    user_ans = answers[spot["id"]].strip().lower()
                    is_corr = (
                        user_ans == spot["label"].lower() or
                        user_ans in [a.lower() for a in spot["alt"]]
                    )
                    if is_corr:
                        correct_count += 1
                    results.append({
                        "id": spot["id"],
                        "user_ans": answers[spot["id"]],
                        "correct": spot["label"],
                        "is_correct": is_corr,
                    })

                st.session_state["diagram_results"] = results
                st.session_state["diagram_correct"] = correct_count
                st.session_state["diagram_total"] = len(spots)
                st.session_state["diagram_choice_for_ai"] = diagram_choice

                # Log the attempt
                record_practice_attempt(
                    user["id"], grade, subj_meta["name"], "Diagram Quiz",
                    diagram_choice.replace("_", " "),
                    f"Diagram label challenge ({diagram_choice})",
                    f"{correct_count}/{len(spots)}",
                    1 if correct_count == len(spots) else 0,
                    tone_mode
                )

        # ---- Results ----
        if st.session_state.get("diagram_results") and st.session_state.get("diagram_choice_for_ai") == diagram_choice:
            results = st.session_state["diagram_results"]
            correct = st.session_state["diagram_correct"]
            total = st.session_state["diagram_total"]

            pct = int((correct / total) * 100) if total else 0

            st.divider()
            st.markdown(f"### 📊 Score: **{correct} / {total}** ({pct}%)")

            if pct == 100:
                st.success("🏆 PERFECT! You know this diagram inside out.")
            elif pct >= 60:
                st.info("✅ Solid effort! Review the ones you missed below.")
            else:
                st.warning("⚠️ Time to study this diagram more carefully.")

            for r in results:
                if r["is_correct"]:
                    st.success(f"✅ **#{r['id']}** — Correct! ({r['correct']})")
                else:
                    st.error(f"❌ **#{r['id']}** — You wrote **{r['user_ans'] or '(blank)'}** | Correct answer: **{r['correct']}**")

            # ---- AI Bonus Question ----
            st.divider()
            st.markdown("### 🤖 AI Bonus Challenge")
            st.caption("Based on the diagram you just labeled, the AI has a new question for you.")

            if st.button("🎲 Generate Bonus Question", key="gen_ai_diagram_q"):
                if groq_client is None:
                    st.error("⚠️ Groq not initialized.")
                else:
                    with st.spinner("🧠 AI is writing a question..."):
                        try:
                            labeled = [s["label"] for s in spots]
                            ai_q = ask_ai_diagram_question(
                                diagram_choice, labeled, subj_meta["name"], grade, tone_mode
                            )
                            st.session_state["ai_diagram_q"] = ai_q
                        except Exception as e:
                            st.error(f"⚠️ {type(e).__name__}: {e}")

            if st.session_state.get("ai_diagram_q"):
                ai_q = st.session_state["ai_diagram_q"]
                st.info(f"**❓ {ai_q.get('question', '')}**")

                with st.expander("💡 Hint"):
                    st.write(ai_q.get("hint", "No hint available."))

                user_bonus = st.text_input("Your answer:", key="ai_diagram_answer")
                if st.button("Submit Bonus", key="submit_ai_diagram"):
                    if user_bonus.strip().lower() == ai_q.get("correct", "").strip().lower():
                        st.success(f"🎉 Correct! **{ai_q.get('correct')}**")
                    else:
                        st.error(f"❌ Not quite. Correct answer: **{ai_q.get('correct')}**")

                    st.markdown("#### 📖 Solution Steps:")
                    for step in ai_q.get("steps", []):
                        st.markdown(f"- {step}")

                    st.session_state["ai_diagram_q"] = None  # Clear for next time
                     # ==================== TAB 13: BOSS FIGHT ====================
    with tab_boss:
        st.markdown("# ⚔️ BOSS FIGHT")
        st.caption(f"Five questions. One health bar. Prove you're ready for **{subj_meta['name']}**.")

        # ---- Setup screen ----
        if st.session_state["boss_state"] is None:
            st.markdown("### 🎮 Rules")
            st.markdown("""
            - **5 questions** from your current subject
            - You start with **100 HP**
            - Every wrong answer costs **20 HP**
            - Answer **4 or more correctly** to win
            - Once you submit an answer, you can't undo it
            """)

            st.markdown(f"**Current Subject:** {subj_meta['icon']} {subj_meta['name']} — Grade {grade}")
            st.markdown(f"**Difficulty:** 60 seconds per question (target)")

            st.divider()

            if st.button("⚔️ BEGIN BOSS FIGHT", type="primary", use_container_width=True, key="start_boss"):
                # Generate 5 questions
                boss_questions = []
                topics_list = subj_meta["topics"].get(grade, ["General"])
                for i in range(5):
                    t = topics_list[i % len(topics_list)]
                    boss_questions.append(generate_lockin_question(subject_id, grade, t, tone_mode))

                st.session_state["boss_state"] = {
                    "questions": boss_questions,
                    "current": 0,
                    "hp": 100,
                    "correct_count": 0,
                    "answers": [],
                    "started_at": datetime.now().strftime("%H:%M:%S"),
                    "finished": False,
                    "outcome": None,  # "win" or "lose"
                }
                st.rerun()

        # ---- Fight in progress ----
        else:
            boss = st.session_state["boss_state"]

            # Header: HP bar + progress
            hp = boss["hp"]
            hp_pct = max(0, hp) / 100.0

            col_hp, col_q = st.columns([3, 1])
            with col_hp:
                st.markdown(f"### ❤️ HEALTH: **{hp} / 100 HP**")
                st.progress(hp_pct)
            with col_q:
                st.metric("Question", f"{boss['current'] + 1} / 5")

            st.divider()

            # ---- Finished? ----
            if boss["finished"]:
                outcome = boss["outcome"]

                if outcome == "win":
                    st.balloons()
                    st.markdown(f"# 🏆 VICTORY!")
                    st.markdown(f"**You defeated the {subj_meta['name']} boss!**")
                    st.markdown(f"**Final Score:** {boss['correct_count']} / 5 correct")
                    st.markdown(f"**Final HP:** {hp} / 100")

                    # Trophy
                    trophy = "🥇" if boss["correct_count"] == 5 else "🏆"
                    st.markdown(f"<div style='text-align:center; font-size: 80px;'>{trophy}</div>", unsafe_allow_html=True)

                    if boss["correct_count"] == 5:
                        st.markdown(f"### 🔥 PERFECT RUN — Flawless Victory!")
                    else:
                        st.markdown(f"### ✅ Boss Slayer")
                else:
                    st.markdown(f"# 💀 DEFEAT")
                    st.markdown(f"**The boss was too strong this time.**")
                    st.markdown(f"**Score:** {boss['correct_count']} / 5 correct")
                    st.markdown(f"**Final HP:** 0 / 100")
                    st.markdown("Don't give up — every champion loses before they win. Rest, review, and try again. 💪")

                st.divider()
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔄 Rematch", use_container_width=True, type="primary"):
                        st.session_state["boss_state"] = None
                        st.rerun()
                with col_b:
                    if st.button("🚪 Exit Boss Fight", use_container_width=True):
                        st.session_state["boss_state"] = None
                        st.rerun()

            # ---- Ask current question ----
            else:
                idx = boss["current"]
                q = boss["questions"][idx]

                st.markdown(f"### 🎯 Question {idx + 1} of 5")
                st.markdown(f"*Topic: {q['topic']}*")
                st.markdown(f"#### {q['question']}")

                if q.get("math_expression"):
                    st.latex(q["math_expression"])

                # Diagram if present
                if q.get("diagram"):
                    svg_html = render_diagram_svg(q["diagram"], q.get("diagram_data", {}))
                    if svg_html:
                        st.components.v1.html(svg_html, height=400, scrolling=False)

                # Hint
                with st.expander(f"💡 Hint ({tone_mode.capitalize()})"):
                    st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))

                # Answer form
                with st.form(f"boss_form_{idx}", clear_on_submit=False):
                    user_ans = st.text_input("Your answer:", key=f"boss_ans_{idx}")
                    submit = st.form_submit_button("⚔️ STRIKE", use_container_width=True, type="primary")

                    if submit and user_ans:
                        # Check answer
                        def normalize(v):
                            return v.strip().lower().replace("cm", "").replace("r", "").replace("x=", "").replace("+", "").replace("%", "").strip()

                        u_norm = normalize(user_ans)
                        c_norm = normalize(q["correct"])

                        is_corr = u_norm == c_norm
                        # Numeric check
                        if not is_corr:
                            try:
                                if "/" in u_norm:
                                    p = u_norm.split("/")
                                    u_num = float(p[0]) / float(p[1])
                                else:
                                    u_num = float(u_norm)
                                if "/" in c_norm:
                                    p = c_norm.split("/")
                                    c_num = float(p[0]) / float(p[1])
                                else:
                                    c_num = float(c_norm)
                                is_corr = abs(u_num - c_num) < 0.001
                            except:
                                pass

                        # Update HP
                        if is_corr:
                            boss["correct_count"] += 1
                        else:
                            boss["hp"] -= 20

                        boss["answers"].append({
                            "question": q["question"],
                            "user": user_ans,
                            "correct": q["correct"],
                            "is_correct": is_corr
                        })

                        # Log attempt
                        record_practice_attempt(
                            user["id"], grade, subj_meta["name"], q["topic"], q["subtopic"],
                            q["question"], user_ans, q["correct"], is_corr, tone_mode
                        )

                        # Move to next OR finish
                        boss["current"] += 1

                        if boss["current"] >= 5 or boss["hp"] <= 0:
                            boss["finished"] = True
                            if boss["correct_count"] >= 4:
                                boss["outcome"] = "win"
                            else:
                                boss["outcome"] = "lose"

                        st.rerun()

        # Exit button (always visible while in fight)
        if st.session_state["boss_state"] is not None and not st.session_state["boss_state"].get("finished"):
            st.divider()
            if st.button("🏳️ Forfeit Match", use_container_width=True, key="forfeit_boss"):
                st.session_state["boss_state"] = None
                st.rerun()   
             # ==================== TAB 14: FORMULA SHEETS ====================
    with tab_formula:
        st.subheader("📐 Formula Sheets & Quick Reference")
        st.caption(f"High-yield formulas, glossary, and memory hooks for {subj_meta['name']}.")

        sheet = AI_FORMULA_SHEETS.get(subject_id)

        if not sheet:
            st.info("⚠️ No formula sheet generated yet. Run `python generate_formula_sheets.py` to create them.")
        else:
            # --- FORMULAS ---
            st.markdown("### 📐 Key Formulas")
            formulas = sheet.get("formulas", [])
            if formulas:
                for f in formulas:
                    with st.expander(f"**{f.get('name', 'Formula')}** — `{f.get('formula', '')}`"):
                        st.markdown(f"**Use when:** {f.get('use_when', 'N/A')}")
            else:
                st.caption("No formulas for this subject.")

            st.divider()

            # --- GLOSSARY ---
            st.markdown("### 📖 Glossary")
            glossary = sheet.get("glossary", [])
            if glossary:
                for g in glossary:
                    st.markdown(f"- **{g.get('term', '')}** — {g.get('definition', '')}")

            st.divider()

            # --- MEMORY HOOKS ---
            st.markdown("### 🧠 Memory Hooks")
            hooks = sheet.get("memory_hooks", [])
            if hooks:
                for h in hooks:
                    with st.expander(f"💡 {h.get('concept', '')}"):
                        st.info(h.get("hook", ""))

            st.divider()
            st.caption("💡 **Study tip:** Read the formula, then look away and try to write it from memory. Repeat 3x.")
           # ==================== TAB 15: EXAM READINESS ====================
    with tab_readiness:
        st.subheader("📅 Exam Readiness Score")
        st.caption(f"How prepared are you for **{subj_meta['name']}** Grade {grade}?")

        readiness = calculate_readiness_score(user["id"], subj_meta["name"], grade, subject_id)
        emoji, label, color = get_readiness_tier(readiness["score"])

        # Big score display
        st.markdown(f"""
        <div style="text-align: center; padding: 30px 0; background: rgba(0,240,255,0.05); border-radius: 16px; border: 2px solid {color};">
            <div style="font-size: 14px; opacity: 0.7; letter-spacing: 2px;">EXAM READINESS</div>
            <div style="font-size: 80px; font-weight: 900; color: {color}; text-shadow: 0 0 30px {color};">{readiness['score']:.0f}%</div>
            <div style="font-size: 24px; margin-top: 8px;">{emoji} <strong>{label}</strong></div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        st.progress(min(readiness["score"] / 100.0, 1.0))
        st.write("")

        # Breakdown
        st.markdown("### 📊 Score Breakdown")

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            st.metric("🎯 Accuracy", f"{readiness['accuracy']}%", help="How often you answer correctly")
        with col_b2:
            st.metric("📚 Coverage", f"{readiness['topics_covered']}/{readiness['topics_total']}", help="Topics you've practiced")
        with col_b3:
            days = readiness['days_since_last']
            if days is None:
                last_str = "Never"
            elif days == 0:
                last_str = "Today"
            elif days == 1:
                last_str = "Yesterday"
            else:
                last_str = f"{days}d ago"
            st.metric("⏰ Last Practice", last_str, help="Recency affects your score")

        st.divider()

        # Recommendation
        st.markdown("### 🎯 What To Do Next")

        if readiness["attempts"] == 0:
            st.info(f"You haven't practiced **{subj_meta['name']}** yet. Head to the Practice tab and answer a few questions to build your score.")
        else:
            weak = find_weakest_topics(user["id"], subj_meta["name"], grade, min_attempts=2, top_n=3)

            if weak:
                st.markdown("**Focus on your weakest topics:**")
                for i, w in enumerate(weak, 1):
                    st.markdown(f"**{i}. {w['topic']}** — `{w['accuracy']:.0f}% accuracy across {w['attempts']} tries`")

            if st.button("🧠 Get AI Coaching Tip", use_container_width=True, type="primary", key="readiness_ai_btn"):
                st.session_state["readiness_ai_active"] = True

            if st.session_state.get("readiness_ai_active"):
                if groq_client is None:
                    st.error("⚠️ Groq client not initialized.")
                else:
                    try:
                        with st.spinner("💭 Analyzing your progress..."):
                            st.write_stream(
                                generate_readiness_advice(
                                    readiness, subj_meta["name"], grade, tone_mode, weak
                                )
                            )
                    except Exception as e:
                        st.error(f"⚠️ {type(e).__name__}: {e}")

        st.divider()
        st.caption("💡 **Tip:** Your score improves by (1) answering correctly, (2) covering more topics, and (3) practicing regularly.")
        # ==================== TAB 16: FULL MOCK PAPER ====================
    with tab_paper:
        st.subheader("📄 Full Mock Paper Generator")
        st.caption(f"Generate a complete CAPS-style exam paper for **{subj_meta['name']}** Grade {grade}.")

        # ---- State: setup / taking / done ----
        if st.session_state["paper_state"] is None:
            st.markdown("### 🎯 Generate a New Paper")
            st.info(f"📝 You'll get a full {50}-mark paper with 8 questions, a mark allocation, and a memo. Then AI will mark your answers.")

            col1, col2 = st.columns(2)
            with col1:
                paper_marks = st.selectbox("Total marks:", [30, 50, 70, 100], index=1)
            with col2:
                paper_time = st.selectbox("Time limit (min):", [30, 45, 60, 90, 120], index=2)

            if st.button("📄 Generate Paper", type="primary", use_container_width=True, key="gen_paper_btn"):
                with st.spinner("📝 Writing your paper... this takes 15-30 seconds"):
                    try:
                        paper = generate_full_paper(subj_meta["name"], grade, paper_marks, paper_time, tone_mode)

                        # Safety: AI sometimes wraps the response in a list
                        if isinstance(paper, list):
                            paper = paper[0] if paper else {}

                        # Safety: if the structure is broken, warn the user
                        if not isinstance(paper, dict) or "sections" not in paper:
                            st.error("⚠️ The AI returned an unexpected format. Click Generate Paper again to retry.")
                        else:
                            st.session_state["paper_state"] = {
                                "paper": paper,
                                "answers": {},
                                "submitted": False,
                                "result_text": "",
                            }
                            st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ {type(e).__name__}: {e}")
        else:
            paper_state = st.session_state["paper_state"]
            paper = paper_state["paper"]

            # ---- Header ----
            st.markdown(f"## {paper.get('title', 'Mock Paper')}")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Marks", paper.get("total_marks", 0))
            col_b.metric("Time", f"{paper.get('time_minutes', 60)} min")
            col_c.metric("Sections", len(paper.get("sections", [])))

            st.markdown("### 📋 Instructions")
            for inst in paper.get("instructions", []):
                st.markdown(f"- {inst}")

            st.divider()

            if paper_state["submitted"]:
                # ---- Show results ----
                st.success("✅ Paper submitted! Here's your marked result:")
                st.markdown("---")
                st.markdown(paper_state["result_text"])

                st.divider()
                col_x, col_y = st.columns(2)
                with col_x:
                    if st.button("🔄 New Paper", use_container_width=True, type="primary"):
                        st.session_state["paper_state"] = None
                        st.rerun()
                with col_y:
                    if st.button("🚪 Exit", use_container_width=True):
                        st.session_state["paper_state"] = None
                        st.rerun()
            else:
                # ---- Show paper for answering ----
                st.markdown("### ✍️ Answer the Questions")

                with st.form("full_paper_form"):
                    all_answers = {}
                    q_counter = 0

                    for section_idx, section in enumerate(paper.get("sections", [])):
                        # Safety: skip malformed sections
                        if not isinstance(section, dict):
                            continue

                        section_name = section.get("name", f"Section {section_idx + 1}")
                        section_marks = section.get("marks", 0)
                        st.markdown(f"### {section_name} — {section_marks} marks")

                        questions = section.get("questions", [])
                        if not isinstance(questions, list):
                            st.warning("⚠️ This section is malformed. Skipping.")
                            continue

                        for q_idx, q in enumerate(questions):
                            # Safety: skip non-dict questions
                            if not isinstance(q, dict):
                                continue

                            q_num = q.get("number", f"{section_idx + 1}.{q_idx + 1}")
                            q_marks = q.get("marks", 0)
                            q_text = q.get("question", "(no question text)")

                            st.markdown(f"**Q{q_num}** ({q_marks} marks)")
                            st.markdown(f"{q_text}")

                            # Show MCQ options if they exist
                            options = q.get("options", [])
                            if isinstance(options, list):
                                for opt in options:
                                    st.markdown(f"- {opt}")

                            all_answers[q_num] = st.text_area(
                                f"Your answer for Q{q_num}:",
                                key=f"paper_ans_{q_num}_{q_counter}",
                                height=100,
                                label_visibility="collapsed",
                                placeholder="For MCQ: write the letter (A/B/C/D). For others: show your working."
                            )
                            st.write("")
                            q_counter += 1

                    submit_paper = st.form_submit_button("📤 Submit Paper", use_container_width=True, type="primary")
                    if submit_paper:
                        paper_state["answers"] = all_answers

                        # Count blanks
                        blanks = sum(1 for v in all_answers.values() if not v.strip())
                        if blanks == len(all_answers):
                            st.warning("⚠️ You haven't answered any questions yet.")

                        with st.spinner("🎓 Your paper is being marked..."):
                            try:
                                result_text = "".join(
                                    mark_full_paper(
                                        paper, all_answers, subj_meta["name"], grade, tone_mode
                                    )
                                )
                                paper_state["result_text"] = result_text
                                paper_state["submitted"] = True

                                # Log the attempt for the dashboard
                                record_practice_attempt(
                                    user["id"],
                                    grade,
                                    subj_meta["name"],
                                    "Full Mock Paper",
                                    paper.get("title", "Mock Paper"),
                                    f"Completed {paper.get('total_marks', 50)}-mark mock paper",
                                    "Submitted",
                                    "Submitted",
                                    1,
                                    tone_mode
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ {type(e).__name__}: {e}")

                st.divider()
                if st.button("🏳️ Cancel Paper", use_container_width=True, key="cancel_paper"):
                    st.session_state["paper_state"] = None
                    st.rerun()

    # ==================== TAB 7: INFO ====================
    with tab_info:
        st.subheader("ℹ️ Official CAPS Curriculum Coverage Guide")
                # ---- About LockIn ----
        with st.expander("📖 About LockIn"):
            st.markdown(f"""
            **LockIn** is a free, offline-first study companion built for South African CAPS learners in Grades 8–12.

            ### 🎯 What it does
            - **Practice Questions** with AI-generated content across 15 CAPS subjects
            - **Smart Notes** in 4 different tones (TikTok, Casual, JJK, Formal)
            - **AI Tutor Chat** that answers any question about your subject
            - **AI Essay Marker** with real DBE rubric scoring
            - **Panic Mode** for last-minute exam prep
            - **Boss Fight** gamified challenge mode
            - **Full Mock Papers** with complete memos and mark allocations

            ### 👥 Who it's for
            Grade 8–12 learners preparing for CAPS exams across all subjects.

            ### 🏗️ How it's built
            Python · Streamlit · SQLite · Groq AI

            ### 💡 Version
            v1.0 — Free forever
            """)

        # ---- Privacy Policy ----
        with st.expander("🔐 Privacy Policy"):
            st.markdown("""
            **Last updated:** October 2026

            ### What We Store
            LockIn stores only what's needed to run your study experience:

            - **Account info:** username, display name, hashed password, grade level
            - **Study data:** your practice attempts, XP, streaks, badges, and essay results
            - **Preferences:** your chosen theme, tone, and learning style

            ### What We Don't Do
            - ❌ We don't sell your data
            - ❌ We don't share it with advertisers
            - ❌ We don't track you across the web
            - ❌ We don't use cookies for tracking

            ### Where Your Data Lives
            Your data is stored securely on the server hosting this app. Passwords are hashed with PBKDF2 (100,000 rounds) — we cannot read them.

            ### AI Processing
            When you use AI features (Practice, Notes, Chat, Essay Marker, Paper Generator), your question or essay is sent to **Groq** for processing. Don't share personal information you wouldn't want processed by an AI.

            ### Your Rights
            You can:
            - **Reset your progress** anytime from the sidebar
            - **Delete your account** by contacting the developer
            - **Log out** to clear your session

            ### Contact
            This is a student-built app. For any privacy concerns, please contact the developer directly.
            """)

        # ---- Terms of Service ----
        with st.expander("📜 Terms of Service"):
            st.markdown("""
            **Last updated:** October 2026

            ### 1. Acceptance
            By signing up and using LockIn, you agree to these terms.

            ### 2. Personal Use
            LockIn is provided as a free study tool for personal, non-commercial use. You may not resell, redistribute, or monetize this service.

            ### 3. AI Content Disclaimer
            AI-generated content (questions, notes, essays, papers) is a **study aid** — not a replacement for your teacher, textbook, or official DBE materials. Always verify important facts with your teacher.

            ### 4. No Guarantees
            We make no promises about exam results. Your success depends on your own effort and understanding.

            ### 5. Account Responsibility
            You are responsible for keeping your password safe. Don't share your account credentials.

            ### 6. Appropriate Use
            Don't use the app to harass others, spam, upload harmful content, or abuse the AI services.

            ### 7. Changes
            These terms may change. Continued use after changes means you accept them.

            ### 8. Termination
            Accounts may be suspended if these terms are violated.

            ### 9. Disclaimer
            LockIn is provided "as is" without warranty. The developer is not liable for any damages arising from use of the app.

            ---

            By using LockIn, you confirm you've read and agreed to these terms.
            """)

        st.divider()
        st.markdown("""
        **LockIn** strictly follows the South African CAPS curriculum:

        #### Senior Phase (Grades 8 & 9)
        - **Mathematics**: Integers, Common Fractions, Pythagoras, Geometry of Straight Lines, Algebra.
        - **Natural Sciences (NS)**: Life & Living (Digestive System, Cells), Matter & Materials (Atoms, Circuits).
        - **EMS**: Accounting Equation (A = OE + L), CRJ, CPJ, Supply & Demand.
        - **Social Sciences (SS)**: Geography (1:50 000 Topographic Mapwork, Contours), History (Mineral Revolution).
        - **Technology**: Class 1, 2, 3 Levers, Mechanisms, Structural Triangulation.
        - **English**: Figures of speech, Active/Passive, Direct/Indirect voice, Concord.
        - **Life Orientation (LO)**: SMART Goals, Self-Development, Career paths.

        #### FET Phase (Grades 10–12)
        - **Mathematics & Maths Lit**: Functions, Calculus, Trigonometry, Municipal Tariffs, Tax.
        - **Physical Sciences**: Newton's Laws, Doppler Effect, Waves, Organic Chemistry.
        - **Life Sciences**: Genetics, Punnett Squares, DNA Replication, Evolution.
        - **Commerce**: Accounting, Business Studies (SWOT, Porter's Five Forces), Economics.
        - **Humanities**: Geography (Synoptic charts), History (Cold War).
        """)
        st.markdown("---")
    st.caption("🎓 LockIn Study Coach • Free for South African learners • Built by someone who understands the struggle")        
        # ============ AUTO-SCROLL TO TOP ON SECTION CHANGE ============
        # ============ AUTO-SCROLL TO TOP ON SECTION CHANGE ============
    if st.session_state.pop("_scroll_to_top", False):
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
                const doScroll = () => {
                    window.parent.scrollTo(0, 0);
                    const bodies = window.parent.document.querySelectorAll('body, .main, section, div');
                    bodies.forEach(el => { if (el.scrollTop) el.scrollTop = 0; });
                };
                doScroll();
                setTimeout(doScroll, 50);
                setTimeout(doScroll, 150);
                setTimeout(doScroll, 400);
            </script>
            """,
            height=0,
        )
    # ============ END AUTO-SCROLL ============
    # ============ END AUTO-SCROLL ============



def adapt_chapter_to_tone(chapter_title, summary, tone, subject_name):
    is_math = "math" in subject_name.lower()
    is_science = any(k in subject_name.lower() for k in ["science", "biology", "life"])
    is_commerce = any(k in subject_name.lower() for k in ["account", "business", "econ", "ems"])

    if tone == "tiktok":
        hook = "🔥 NO CAP FR FR: LOCK IN ON THIS CHAPTER"
        slang_sum = f"Fam, if you get this question in Paper 1 or Paper 2, DO NOT get cooked! {summary} Basically, markers expect you to flex the exact steps. Master the formula, don't drop negative signs, and you will literally eat and leave no crumbs."
        if is_math:
            hook = "📱 MATHS TIKTOK CHEAT CODE: ATE AND LEFT NO CRUMBS"
            slang_sum = f"Bro, this maths chapter is pure main character energy if you know the pattern. {summary} Stop doing mental gymnastics—isolate your variables, follow the DBE formula sheet, and collect your 5 free marks before the examiner even blinks."
        elif is_science:
            hook = "🧬 SCIENCE TIKTOK VIBE: RIZ MASTERY GUIDE"
            slang_sum = f"Bestie, high-key you cannot just vibe your way through biology/physics definitions. {summary} DBE markers have a literal checklist of buzzwords. If the buzzword is missing, you are cooked fr. Memorize the diagram pathways and secure that Level 7 bag."
        elif is_commerce:
            hook = "💰 COMMERCE MONEY MOVES: ZERO CAP"
            slang_sum = f"Listen up future CEO: in this chapter, {summary} It is literally a balancing act. If your debits and credits or PESTLE factors do not align, you are giving broke energy on the memo. Lock in and secure the easy marks."

        return {
            "hook": hook,
            "badge": "🔥 TikTok Slang Mode (Gen Z)",
            "summary": slang_sum,
            "takeaways": [
                "⚡ Cheat Code 1: Never skip writing down the base formula first—it is a free 1-mark safety net.",
                "⚡ Cheat Code 2: Spot the examiner trap early so you do not take a massive L on question 2.",
                "⚡ Cheat Code 3: Practice this with a 2-minute timer on your phone so you stay clutch under pressure."
            ],
            "pitfall": "💀 How Markers Try to Cook You: Rushing through signs or leaving out units (like N, m/s, or Rands) is literally giving away free marks for nothing. Do not fumble the bag!",
            "tip": "🚀 TikTok Brainrot Hack: Turn the 3 main definitions into an audio voice note or rhythm—you will remember it instantly in the exam hall."
        }

    if tone == "casual":
        hook = "☕ LEKKER MZANSI STUDY WALKTHROUGH"
        casual_sum = f"Sharp sharp! Let's unpack this together without the scary textbook jargon. {summary} Once you see the pattern behind how they set matric past papers, this actually becomes one of the most scoring sections in the entire syllabus."
        if is_math:
            hook = "📐 LEKKER MATHS BREAKDOWN (MZANSI STYLE)"
            casual_sum = f"Eish, learners often panic when they see this in Paper 1, but check how simple it really is: {summary} Just take it step by step, keep your working neat so the marker can award method marks, and you are good to go!"
        elif is_science:
            hook = "🔬 CHILL SCIENCE CHAT: EASY MARKS"
            casual_sum = f"Listen here chief, don't let the big scientific words intimidate you. {summary} Think of the diagrams as a story (like food traveling down the gut or electrons flowing in a loop). Connect each part to its real function."
        elif is_commerce:
            hook = "💼 CHILL BUSINESS & NUMBERS TALK"
            casual_sum = f"Lekker vibes! In business and accounting, everything tells a story about money or resources: {summary} Keep the core equation or framework in mind, and you will cruise through the case studies."

        return {
            "hook": hook,
            "badge": "☕ ZA Casual Lekker Vibe",
            "summary": casual_sum,
            "takeaways": [
                "💡 Tip 1: Highlight key question words like 'Describe', 'Calculate', or 'Justify'.",
                "💡 Tip 2: Show every single working line—DBE markers love awarding CA (Consistent Accuracy) marks.",
                "💡 Tip 3: Draw a quick rough sketch or write the formula in the margin before solving."
            ],
            "pitfall": "⚠️ Common Student Slip-up: Forgetting to state reasons in geometry or forgetting the final conclusion sentence in business case studies.",
            "tip": "✨ Matric Secret: Start your revision with past exam papers from 2021-2024 to see the exact variations the examiners love repeating."
        }
    if tone == "jjk":
        hook = "⚔️ DOMAIN EXPANSION: INFINITE FOCUS"
        jjk_sum = f"Listen, champion. This chapter is your next mission. {summary} The examiner's cursed energy is strong, but your technique is stronger — IF you master the fundamentals. Complete your Reverse Cursed Technique by practising until you can do it without thinking."
        if is_math:
            hook = "📐 CURSED TECHNIQUE: FORMULA MASTERY"
            jjk_sum = f"Every formula is a cursed technique, and every question is a cursed spirit. {summary} Reach Grade 1 by mastering the steps. Land a Black Flash by getting 100% on your next attempt. Lock in."
        elif is_science:
            hook = "🧬 DOMAIN EXPANSION: CONCEPT MASTERY"
            jjk_sum = f"Knowledge is your cursed energy. {summary} To reach Special Grade, you must memorize the pathways and understand the flow. Every definition you skip is a cursed spirit waiting to ambush you in the exam hall."
        elif is_commerce:
            hook = "💰 CURSED TECHNIQUE: BALANCE MASTERY"
            jjk_sum = f"Every transaction has cursed energy — debits and credits in perfect balance. {summary} Reach Special Grade by mastering the equation, and the examiner's domain won't affect you."

        return {
            "hook": hook,
            "badge": "⚔️ JJK champion Mode",
            "summary": jjk_sum,
            "takeaways": [
                "⚔️ Mission 1: Master the fundamental technique before attempting complex missions.",
                "⚔️ Mission 2: Practice under pressure — the Shibuya Incident exam is coming.",
                "⚔️ Mission 3: Land Black Flash by locking in for 25 focused minutes a day."
            ],
            "pitfall": "💀 Cursed Spirit Alert: Sign errors, missing units, and skipped steps are ambushes. Do not fall for them.",
            "tip": "🚀 champion's Path: Do 3 practice questions in a row correctly to unlock Reverse Cursed Technique."
        }
    return {
        "hook": "🎓 OFFICIAL DBE CAPS EXAMINATION & RUBRIC STANDARD",
        "badge": "📜 Formal CAPS DBE Academic Standard",
        "summary": f"Curriculum and Assessment Policy Statement (CAPS) Prescribed Standard: {summary} Candidates are formally assessed on cognitive levels 1 through 4 (Knowledge, Routine Procedures, Complex Procedures, and Problem Solving). Full mathematical and scientific justification is mandatory.",
        "takeaways": [
            "📌 Criterion 1: Verbatim adherence to official DBE definition glossaries is required for full credit.",
            "📌 Criterion 2: In multi-step algorithmic derivations, every intermediate transformation must be documented to qualify for Method (M) and Accuracy (A) marks.",
            "📌 Criterion 3: Final numerical values must be expressed with standard SI units and rounded to exactly two decimal places unless otherwise stipulated."
        ],
        "pitfall": "⚖️ Formal Mark Allocation Caution: Omitting units, failure to provide geometric statements with accredited abbreviations (e.g., [tan-chord thm]), or presenting unjustified final answers will incur immediate mark forfeiture.",
        "tip": "📜 Assessment Rubric Strategy: Review the DBE National Diagnostic Reports to identify historical national error trends and prioritize high-weighting syllabus sub-topics."
    }

def get_diagram_for_chapter(ch_title, subject_id):
    t = ch_title.lower()
    s = subject_id.lower()
    if any(k in t for k in ["digestive", "human body", "alimentary", "organ"]) or (s == "natural_sciences" and "body" in t):
        return "human_digestive"
    if any(k in t for k in ["heart", "circulat", "blood", "cardio"]):
        return "human_heart"
    if any(k in t for k in ["cell", "tissue", "photosynthesis"]):
        return "plant_cell"
    if any(k in t for k in ["circuit", "electric", "ohm", "resistor"]):
        return "electric_circuit"
    if any(k in t for k in ["lens", "optics", "light", "refraction"]):
        return "optics_lens"
    if any(k in t for k in ["parabola", "quadratic", "function", "algebra"]):
        return "cartesian_parabola"
    if any(k in t for k in ["accounting equation", "general ledger", "balance sheet"]):
        return "accounting_scale"
    if any(k in t for k in ["environment", "pestle", "porter", "business role"]):
        return "business_environments"
    if any(k in t for k in ["circular flow", "macroeconomic", "national income", "gdp"]):
        return "economic_circular_flow"
    if any(k in t for k in ["pythagoras", "triangle"]):
        return "pythagoras"
    if any(k in t for k in ["contour", "topograph", "geography"]):
        return "contour_map"
    return None

if __name__ == "__main__":
    main()








