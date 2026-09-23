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

# ---------------------------------------------------------
# 1. DATABASE & PERSISTENT STREAK SETUP (SQLite)
# ---------------------------------------------------------
DB_FILE = "lockin_study_coach.db"

def init_db():
    """Initialise SQLite tables for practice attempts and daily streak."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS streak_data (
            id INTEGER PRIMARY KEY,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_date TEXT DEFAULT ''
        )
    """)
    c.execute("SELECT COUNT(*) FROM streak_data WHERE id = 1")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO streak_data (id, current_streak, longest_streak, last_date) VALUES (1, 0, 0, '')")
    conn.commit()
    conn.close()

def get_streak_info():
    """Retrieve current daily streak data."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT current_streak, longest_streak, last_date FROM streak_data WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return 0, 0, ""
    return row[0], row[1], row[2]

def record_practice_attempt(grade, subject, topic, subtopic, question, user_ans, correct_ans, is_correct, tone):
    """Save user attempt and update daily streak."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = date.today().isoformat()

    c.execute("""
        INSERT INTO attempts (grade, subject, topic, subtopic, question, user_answer, correct_answer, is_correct, tone, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (grade, subject, topic, subtopic, question, str(user_ans), str(correct_ans), 1 if is_correct else 0, tone, now_str))

    c.execute("SELECT current_streak, longest_streak, last_date FROM streak_data WHERE id = 1")
    curr, longest, last_d = c.fetchone()

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
        c.execute("UPDATE streak_data SET current_streak = ?, longest_streak = ?, last_date = ? WHERE id = 1",
                  (curr, longest, today_str))

    conn.commit()
    conn.close()

def get_attempts_df():
    """Fetch stored practice records."""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM attempts", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def reset_all_data():
    """Reset database when student requests a clean slate."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM attempts")
    c.execute("UPDATE streak_data SET current_streak = 0, longest_streak = 0, last_date = '' WHERE id = 1")
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
# 1C. JJK RONIN CURSED NOTES (All Subjects, All Grades)
# ---------------------------------------------------------
JJK_NOTES = {
    "mathematics": {
        "subject_name": "Mathematics",
        "opening": "Alright, ronin. Listen up. Mathematics isn't a school subject. It's the universe's innate domain. Every theorem is a binding vow the cosmos made with itself. You don't 'learn' math — you exorcise ignorance.",
        "domain_expansion": "Domain Expansion: Infinite Precision",
        "curse_level": "Special Grade (DBE Paper 1 & 2)",
        "sure_hit": "Every question has a sure-hit technique. Identify the technique (formula) before you strike.",
        "reverse_cursed_technique": "Check your working backwards. If the answer doesn't substitute correctly, your technique failed.",
        "black_flash": "Landing a perfect solution in under 30 seconds of reading the question = Black Flash. Practice until you can land it consistently.",
        "binding_vow": "Never skip a step. Show every line of working. Method marks are cursed energy you can't afford to waste.",
        "cursed_tools": [
            "Formula sheet (memorize it like a cursed technique)",
            "Pencil and eraser (your cursed tools)",
            "Past papers (cursed spirits to exorcise)"
        ],
        "final_word": "Throughout heaven and earth, only your worked solutions are real."
    },
    "natural_sciences": {
        "subject_name": "Natural Sciences",
        "opening": "Alright, ronin. Listen up. Natural Sciences is the study of cursed energy in the physical and living world. Every reaction, every cell, every circuit is a cursed technique in motion.",
        "domain_expansion": "Domain Expansion: Living Systems",
        "curse_level": "Grade 1 (Grades 8 & 9)",
        "sure_hit": "The digestive system is a cursed pipeline. The electric circuit is a cursed loop. Learn the flow, and you control the domain.",
        "reverse_cursed_technique": "Test your knowledge by explaining concepts out loud. If you can't teach it, you don't control it.",
        "black_flash": "Drawing a perfect diagram from memory = Black Flash. Diagram marks are free cursed energy.",
        "binding_vow": "Buzzwords are binding vows. If the DBE mark scheme requires 'peristalsis', writing 'moving food' fails the vow.",
        "cursed_tools": [
            "Diagrams (your map of the cursed domain)",
            "Buzzword glossary (your cursed technique scroll)",
            "Practical investigations (real-world cursed energy)"
        ],
        "final_word": "The universe's innate domain is biology. Its sure-hit is homeostasis."
    },
    "ems": {
        "subject_name": "Economic & Management Sciences",
        "opening": "Alright, ronin. Listen up. EMS is the study of cursed energy flow — money, resources, and the invisible forces that govern wealth. Every transaction is a binding vow between debit and credit.",
        "domain_expansion": "Domain Expansion: The Accounting Equation",
        "curse_level": "Grade 1 (Grades 8 & 9)",
        "sure_hit": "A = O + L. This is the sure-hit. If your equation doesn't balance, your cursed technique failed.",
        "reverse_cursed_technique": "Reverse-engineer every transaction. If you know the effect, you can trace the source.",
        "black_flash": "Balancing a full trial balance with zero errors = Black Flash. This is the ultimate cursed technique.",
        "binding_vow": "DEAD CLIC is your binding vow: Debit Expenses, Assets, Drawings — Credit Liabilities, Income, Capital. Break this vow and your books won't balance.",
        "cursed_tools": [
            "T-Accounts (your cursed ledger)",
            "Source documents (the origin of every cursed transaction)",
            "Financial statements (your domain's true form)"
        ],
        "final_word": "Throughout heaven and earth, every debit has an equal and opposite credit."
    },
    "social_sciences": {
        "subject_name": "Social Sciences",
        "opening": "Alright, ronin. Listen up. Social Sciences is the study of cursed history and cursed geography. Every map is a domain. Every war is a cursed spirit born from human conflict.",
        "domain_expansion": "Domain Expansion: Time and Space",
        "curse_level": "Grade 1 (Grades 8 & 9)",
        "sure_hit": "Contour lines reveal the terrain's true form. Map scales convert the cursed distance.",
        "reverse_cursed_technique": "Analyze causes and consequences. Every event has a binding vow to what came before and what follows.",
        "black_flash": "Quoting a primary source with correct dates and context = Black Flash. Historians respect the perfect citation.",
        "binding_vow": "Always link back to the question. A wandering answer is a broken binding vow.",
        "cursed_tools": [
            "1:50 000 topographic maps (your terrain domain)",
            "Timeline scrolls (your cursed chronology)",
            "Primary sources (the original cursed energy)"
        ],
        "final_word": "Those who forget history are exorcised by it."
    },
    "technology": {
        "subject_name": "Technology",
        "opening": "Alright, ronin. Listen up. Technology is the art of building cursed tools. Every lever, every gear, every circuit is a cursed mechanism that multiplies your power.",
        "domain_expansion": "Domain Expansion: Mechanical Advantage",
        "curse_level": "Grade 1 (Grades 8 & 9)",
        "sure_hit": "FLE 1-2-3 is the sure-hit. Fulcrum in middle = Class 1. Load in middle = Class 2. Effort in middle = Class 3.",
        "reverse_cursed_technique": "Disassemble the mechanism in your mind. Every system can be broken into smaller cursed techniques.",
        "black_flash": "Building a working prototype with your own hands = Black Flash. Real cursed tools are forged, not bought.",
        "binding_vow": "Never skip the design process. Sketch, build, test, improve. The binding vow of the engineer.",
        "cursed_tools": [
            "Levers, gears, and pulleys (your physical cursed techniques)",
            "Triangulation (your structural binding vow)",
            "Circuits (your electrical cursed energy)"
        ],
        "final_word": "Throughout heaven and earth, only the well-designed tool is real."
    },
    "physical_sciences": {
        "subject_name": "Physical Sciences",
        "opening": "Alright, ronin. Listen up. Physics isn't a school subject. It's the universe's innate domain. Every law is a binding vow the cosmos made with itself. You don't 'learn' physics—you exorcise ignorance.",
        "domain_expansion": "Domain Expansion: Thermodynamics",
        "curse_level": "Special Grade (Grades 10-12)",
        "sure_hit": "The First Law is a binding vow: energy cannot be created or destroyed, only converted. Every motion converts cursed energy.",
        "reverse_cursed_technique": "Reverse Cursed Technique can heal a local calculation, but it doesn't erase entropy—it just pays the cost elsewhere.",
        "black_flash": "F = ma. Apply force, and mass accelerates. Land a perfect free-body diagram + correct equation = Black Flash.",
        "binding_vow": "Every action has an equal and opposite reaction. Newton's Third Law is the universe's eternal binding vow.",
        "cursed_tools": [
            "Free-body diagrams (your map of cursed forces)",
            "Formula sheet (your cursed technique scroll)",
            "Past papers (cursed spirits to exorcise)"
        ],
        "final_word": "The universe's innate domain is math. Its sure-hit is entropy. Throughout heaven and earth, you alone are made of quantized fields."
    },
    "life_sciences": {
        "subject_name": "Life Sciences",
        "opening": "Alright, ronin. Listen up. Life Sciences is the study of the cursed code of life. DNA is a binding vow written in base pairs. Every cell is a domain of cursed energy in motion.",
        "domain_expansion": "Domain Expansion: DNA Replication",
        "curse_level": "Special Grade (Grades 10-12)",
        "sure_hit": "A pairs with T. C pairs with G. In RNA, A pairs with U. Break the binding vow of base pairing, and the whole sequence mutates.",
        "reverse_cursed_technique": "Read the Punnett square backwards. If you know the offspring ratio, you can trace the parent genotypes.",
        "black_flash": "Drawing a perfect Punnett square with P1, meiosis, gametes, fertilisation, F1 genotypes, and phenotypes = Black Flash. These are format marks you can't afford to lose.",
        "binding_vow": "In sex-linked disorders, the allele is carried ONLY on the X chromosome. This is an unbreakable cursed vow.",
        "cursed_tools": [
            "Punnett squares (your cursed probability domain)",
            "Pedigree diagrams (your cursed lineage scroll)",
            "Gene sequences (the raw cursed code)"
        ],
        "final_word": "Throughout heaven and earth, only natural selection is absolute."
    },
    "accounting": {
        "subject_name": "Accounting",
        "opening": "Alright, ronin. Listen up. Accounting is the cursed ledger of every financial soul. Every transaction is a binding vow between debit and credit, recorded for eternity.",
        "domain_expansion": "Domain Expansion: General Ledger",
        "curse_level": "Grade 1 to Special Grade (Grades 10-12)",
        "sure_hit": "Assets = Owner's Equity + Liabilities. This is the sure-hit. If your equation doesn't balance, your whole domain collapses.",
        "reverse_cursed_technique": "Reconcile the bank statement. Every discrepancy is a cursed spirit that must be exorcised before the books balance.",
        "black_flash": "Preparing a full set of financial statements with zero errors = Black Flash. This is Special Grade technique.",
        "binding_vow": "GAAP principles are binding vows. Break them, and your financial statements are cursed.",
        "cursed_tools": [
            "T-Accounts (your cursed ledger)",
            "Bank reconciliation statements (your cursed balance)",
            "Financial ratios (your diagnostic cursed technique)"
        ],
        "final_word": "Throughout heaven and earth, only the balanced ledger is real."
    },
    "business_studies": {
        "subject_name": "Business Studies",
        "opening": "Alright, ronin. Listen up. Business Studies is the study of cursed business environments. Every decision a CEO makes is a cursed technique that ripples through micro, market, and macro domains.",
        "domain_expansion": "Domain Expansion: Micro, Market, Macro",
        "curse_level": "Grade 1 to Special Grade (Grades 10-12)",
        "sure_hit": "SWOT analysis is your sure-hit. Strengths and Weaknesses are internal cursed energy you control. Opportunities and Threats are external cursed spirits you must adapt to.",
        "reverse_cursed_technique": "Porter's Five Forces is your reverse cursed technique. Analyze the competitive landscape to neutralize external threats.",
        "black_flash": "Writing a business essay with Introduction, Body, and Conclusion (LASO format) with correct headings = Black Flash. This is DBE-required cursed technique.",
        "binding_vow": "The business environment is a binding vow. Adapt or be exorcised by change.",
        "cursed_tools": [
            "SWOT matrix (your cursed assessment scroll)",
            "Porter's Five Forces (your competitive cursed technique)",
            "PESTLE analysis (your macro cursed vision)"
        ],
        "final_word": "Throughout heaven and earth, only adaptive businesses survive."
    },
    "economics": {
        "subject_name": "Economics",
        "opening": "Alright, ronin. Listen up. Economics is the study of cursed energy flow — money, resources, and the invisible forces that move markets. Every transaction is a binding vow between buyer and seller.",
        "domain_expansion": "Domain Expansion: Circular Flow",
        "curse_level": "Special Grade (Grades 10-12)",
        "sure_hit": "Injections = Leakages. When I + G + X = S + T + M, the economy is in equilibrium. This is the sure-hit of macroeconomics.",
        "reverse_cursed_technique": "Reverse-engineer every graph. If you know the outcome, trace it back to the cause.",
        "black_flash": "Calculating GDP = C + I + G + (X - M) with all correct components = Black Flash.",
        "binding_vow": "Every cause has an effect. Every price change triggers a response. This is the binding vow of economics.",
        "cursed_tools": [
            "Circular flow diagrams (your macro domain)",
            "Supply and demand graphs (your market cursed technique)",
            "Past exam papers (cursed spirits to exorcise)"
        ],
        "final_word": "Throughout heaven and earth, only supply and demand are absolute."
    },
    "geography": {
        "subject_name": "Geography",
        "opening": "Alright, ronin. Listen up. Geography is the study of cursed earth and cursed sky. Every climate, every mountain, every river is a domain shaped by binding vows of nature.",
        "domain_expansion": "Domain Expansion: Synoptic Chart",
        "curse_level": "Special Grade (Grades 10-12)",
        "sure_hit": "Mid-latitude cyclones move WEST to EAST in the Southern Hemisphere. Clockwise circulation around low pressure. This is the sure-hit of SA climate.",
        "reverse_cursed_technique": "Read the contour lines backward. Steep gradients hide in closely packed lines.",
        "black_flash": "Drawing a perfect cross-section from a synoptic chart with correct labels = Black Flash. Diagram marks are cursed energy you can't afford to lose.",
        "binding_vow": "1:50 000 scale means 1 cm = 0.5 km. Break this binding vow, and your distance calculations are cursed.",
        "cursed_tools": [
            "Topographic maps (your terrain domain)",
            "Synoptic charts (your weather cursed technique)",
            "Cross-sections (your vertical cursed vision)"
        ],
        "final_word": "Throughout heaven and earth, only the topography is real."
    },
    "history": {
        "subject_name": "History",
        "opening": "Alright, ronin. Listen up. History is the study of cursed memory. Every war, every revolution, every struggle is a cursed spirit born from human choices. You don't 'learn' history — you exorcise the past.",
        "domain_expansion": "Domain Expansion: The Cold War",
        "curse_level": "Special Grade (Grades 10-12)",
        "sure_hit": "In source analysis, use O-P-V-L: Origin, Purpose, Value, Limitations. This is the sure-hit of every History source question.",
        "reverse_cursed_technique": "Trace every consequence back to its cause. If you know the outcome, reverse-engineer the cursed event.",
        "black_flash": "Writing an essay with a clear line of argument, primary source evidence, and historiography = Black Flash.",
        "binding_vow": "Every historical claim must be supported by evidence. Opinions without evidence are cursed.",
        "cursed_tools": [
            "Primary sources (the original cursed energy)",
            "Timeline scrolls (your cursed chronology)",
            "Historiography (your academic cursed vision)"
        ],
        "final_word": "Those who forget history are exorcised by it."
    },
    "maths_lit": {
        "subject_name": "Mathematical Literacy",
        "opening": "Alright, ronin. Listen up. Mathematical Literacy is the study of cursed real-world mathematics. Every tariff, every loan, every tax bracket is a cursed technique you must master to survive in the modern world.",
        "domain_expansion": "Domain Expansion: Municipal Tariffs",
        "curse_level": "Grade 1 (Grades 10-12)",
        "sure_hit": "Stepped tariffs are the sure-hit. Calculate each block separately. NEVER multiply the whole usage by the top rate.",
        "reverse_cursed_technique": "VAT calculations: Price inclusive / 1.15 = price exclusive. Reverse the binding vow of tax.",
        "black_flash": "Calculating income tax using SARS tax brackets with all rebates correctly applied = Black Flash.",
        "binding_vow": "Always round money to 2 decimal places. This is the binding vow of financial math.",
        "cursed_tools": [
            "SARS tax tables (your cursed tax domain)",
            "Municipal tariff graphs (your cursed utility technique)",
            "Exchange rate charts (your cursed global vision)"
        ],
        "final_word": "Throughout heaven and earth, only correctly calculated money is real."
    },
    "english": {
        "subject_name": "English (HL & FAL)",
        "opening": "Alright, ronin. Listen up. English is the study of cursed words. Every metaphor, every simile, every rhetorical device is a cursed technique that shapes reality through language.",
        "domain_expansion": "Domain Expansion: Figures of Speech",
        "curse_level": "Grade 1 (Grades 8-12)",
        "sure_hit": "Identify the technique, quote the words, explain the literal meaning, explain the figurative effect. This 4-step is the sure-hit of every poetry and comprehension question.",
        "reverse_cursed_technique": "In passive voice, the object becomes the subject. The binding vow of grammar is reversible.",
        "black_flash": "Writing a summary in 7 concise points without lifting phrases from the original = Black Flash.",
        "binding_vow": "Never name a figure of speech without explaining its effect. This is the binding vow of literature analysis.",
        "cursed_tools": [
            "Figures of speech (your cursed rhetorical technique)",
            "Active and passive voice (your reversible grammar vow)",
            "Visual literacy (your cursed visual technique)"
        ],
        "final_word": "Throughout heaven and earth, only the well-argued essay is real."
    },
    "life_orientation": {
        "subject_name": "Life Orientation",
        "opening": "Alright, ronin. Listen up. Life Orientation is the study of cursed self-mastery. Every goal, every decision, every relationship is a binding vow with your future self.",
        "domain_expansion": "Domain Expansion: SMART Goals",
        "curse_level": "Grade 1 (Grades 8-12)",
        "sure_hit": "SMART is the sure-hit: Specific, Measurable, Achievable, Relevant, Time-bound. Every academic goal must satisfy all five criteria.",
        "reverse_cursed_technique": "Reverse-engineer your failures. If you didn't achieve your goal, one of the SMART criteria was broken.",
        "black_flash": "Using the P-E-E formula (Point, Explain, Example) in a Life Orientation essay = Black Flash.",
        "binding_vow": "Never give one-word answers in LO. The examiner demands explanation. This is the binding vow of LO.",
        "cursed_tools": [
            "SMART goal worksheet (your cursed planner)",
            "Study timetable (your cursed schedule)",
            "Peer pressure refusal scripts (your cursed shield)"
        ],
        "final_word": "Throughout heaven and earth, only the self-aware sorcerer ronin is free."
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
        "bg": "#fff1f5",
        "card": "#ffffff",
        "text": "#47182b",
        "accent": "#ec4899",
        "secondary": "#a855f7",
        "pink": "#f43f5e",
        "border": "rgba(236,72,153,0.3)",
        "glow": "0 0 15px rgba(236,72,153,0.15)"
    },
    "dark_academia": {
        "name": "📜 Dark Academia Scholar",
        "bg": "#181411",
        "card": "#241e1a",
        "text": "#ebdccc",
        "accent": "#d97706",
        "secondary": "#b45309",
        "pink": "#f59e0b",
        "border": "rgba(217,119,6,0.35)",
        "glow": "0 0 12px rgba(217,119,6,0.2)"
    },
    "lofi_sunset": {
        "name": "🌆 Lofi Sunset Chill",
        "bg": "#1c1427",
        "card": "#2a1e3b",
        "text": "#fce7f3",
        "accent": "#f43f5e",
        "secondary": "#f97316",
        "pink": "#ec4899",
        "border": "rgba(244,63,94,0.35)",
        "glow": "0 0 16px rgba(244,63,94,0.25)"
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
           "jjk_ronin": {
        "name": "⚔️ JJK Ronin",
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

def inject_theme_css(theme_key):
    """Inject rich visual styling aligned with the selected aesthetic theme."""
    t = AESTHETICS.get(theme_key, AESTHETICS["cyberpunk_neon"])
    is_cyber = (theme_key == "cyberpunk_neon")
    is_jjk = (theme_key == "jjk_ronin")

    if is_jjk:
            extra_css = """
        /* ⚔️ JJK Ronin — Cursed Energy Domain (Red + Purple + Silver) */
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

    # Generic fallback diagram for any other case
    return f"""
    <div style="text-align: center; margin: 12px 0;">
        <svg viewBox="0 0 260 80" width="280" height="80" style="background: rgba(255,255,255,0.04); border-radius: 12px; border: 1px dashed rgba(255,255,255,0.2);">
            <text x="130" y="45" fill="#94a3b8" font-size="12" font-weight="bold" text-anchor="middle">CAPS Diagnostic Visual</text>
        </svg>
    </div>
    """

# ---------------------------------------------------------
# 5. PROCEDURAL QUESTION GENERATORS WITH ALL 3 TONE MODES
# ---------------------------------------------------------
def generate_lockin_question(subject_id, grade, active_topic, tone_mode):
    """Generate dynamic questions with authentic CAPS content, written math, and diagrams."""
    q_id = f"{subject_id}-{grade}-{random.randint(1000, 9999)}"

    # 1. Mathematics
    if subject_id == "mathematics":
        if "Integer" in active_topic:
            sub_type = random.choice([1, 2])
            if sub_type == 1:
                a = random.randint(3, 11)
                b = random.randint(2, 9)
                ans = -a + b
                return {
                    "id": q_id,
                    "grade": grade,
                    "subject": "Mathematics",
                    "topic": "Integers",
                    "subtopic": "Subtracting Negative Integers",
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
                    "id": q_id,
                    "grade": grade,
                    "subject": "Mathematics",
                    "topic": "Integers",
                    "subtopic": "Multiplying Negative Integers",
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
                "id": q_id,
                "grade": grade,
                "subject": "Mathematics",
                "topic": "Common Fractions",
                "subtopic": "Addition of Fractions (Written Standard)",
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
                "id": q_id,
                "grade": grade,
                "subject": "Mathematics",
                "topic": "Theorem of Pythagoras",
                "subtopic": "Calculating Hypotenuse",
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
            # Geometry of Straight Lines / Linear
            angle = random.choice([65, 70, 75, 110, 115, 120])
            ans = 180 - angle
            return {
                "id": q_id,
                "grade": grade,
                "subject": "Mathematics",
                "topic": "Geometry of Straight Lines",
                "subtopic": "Adjacent Angles on a Line",
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

    # 2. Natural Sciences (NS - Gr 8-9)
    elif subject_id == "natural_sciences":
        if "Digestive" in active_topic:
            return {
                "id": q_id,
                "grade": grade,
                "subject": "Natural Sciences",
                "topic": "Human Digestive System",
                "subtopic": "Organ Functions & Enzymes",
                "question": "Which organ in the human alimentary canal produces hydrochloric acid (HCl) and the enzyme pepsin to churn and chemically digest proteins?",
                "correct": "stomach",
                "steps": [
                    "The stomach is a muscular J-shaped organ.",
                    "Its gastric glands secrete hydrochloric acid (HCl) to kill bacteria and create an acidic pH (~2).",
                    "Pepsin enzyme digests proteins into peptide chains in the **stomach**."
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
                "id": q_id,
                "grade": grade,
                "subject": "Natural Sciences",
                "topic": "Atoms & Periodic Table",
                "subtopic": "Atomic Structure",
                "question": "An atom of Carbon has an atomic number (Z) of 6 and a mass number (A) of 12. How many neutrons are inside its nucleus?",
                "correct": "6",
                "steps": [
                    "Formula: Number of Neutrons = Mass Number (A) - Atomic Number (Z)",
                    "Neutrons = 12 - 6 = **6**"
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

    # 3. EMS (Gr 8-9)
    elif subject_id == "ems":
        a = 150000
        l = 60000
        o = a - l
        return {
            "id": q_id,
            "grade": grade,
            "subject": "EMS",
            "topic": "The Accounting Equation",
            "subtopic": "Assets = Owner's Equity + Liabilities",
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

    # 4. Social Sciences (Gr 8-9)
    elif subject_id == "social_sciences":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Social Sciences",
            "topic": "Topographic Maps & Contours",
            "subtopic": "Contour Line Reading",
            "question": "On a South African 1:50 000 topographic map, when brown contour lines are drawn very close together, does this indicate a STEEP slope or a GENTLE slope?",
            "correct": "steep",
            "steps": [
                "Contour lines join points of equal altitude above sea level.",
                "When contour lines are closely spaced, elevation changes rapidly over a short horizontal distance.",
                "Therefore, closely spaced contours represent a **steep** slope / cliff."
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

    # 5. Technology (Gr 8-9)
    elif subject_id == "technology":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Technology",
            "topic": "Mechanisms & Levers",
            "subtopic": "Classes of Levers",
            "question": "A pair of scissors and a see-saw have the fulcrum positioned in the middle, between the effort and the load. Which class of lever is this (Class 1, Class 2, or Class 3)?",
            "correct": "1",
            "steps": [
                "Class 1 Lever: Fulcrum is in the middle (between Effort and Load). Examples: See-saw, crowbar, scissors.",
                "Class 2 Lever: Load is in the middle. Example: Wheelbarrow.",
                "Class 3 Lever: Effort is in the middle. Example: Tweezers, fishing rod.",
                "Answer: **Class 1**"
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

    # 6. Physical Sciences (Gr 10-12)
    elif subject_id == "physical_sciences":
        m = random.choice([5, 10, 15, 20])
        a = random.choice([2, 3, 4])
        f_k = random.choice([10, 15, 20])
        f_net = m * a
        f_app = f_net + f_k
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Physical Sciences",
            "topic": "Newton's Laws of Motion",
            "subtopic": "Newton's 2nd Law",
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
                "formal": "Correct. Newton’s Second Law applied accurately."
            }
        }

    # 7. Life Sciences (Gr 10-12)
    elif subject_id == "life_sciences":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Life Sciences",
            "topic": "Genetics & Inheritance",
            "subtopic": "Monohybrid Cross (Punnett Square)",
            "question": "Two heterozygous black guinea pigs (Bb x Bb) are crossed. What percentage (%) of the offspring is expected to have the homozygous recessive genotype (bb)?",
            "correct": "25",
            "steps": [
                "Set up 2x2 Punnett square with gametes: B and b from both parents.",
                "Offspring genotypes: 1 BB (25%), 2 Bb (50%), 1 bb (25%).",
                "Percentage for bb = **25%**"
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

    # 8. Accounting (Gr 10-12)
    elif subject_id == "accounting":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Accounting",
            "topic": "Financial Statements & Ledger",
            "subtopic": "General Ledger Accounts",
            "question": "In the General Ledger of a business, does the Bank Account increase on the DEBIT side or the CREDIT side?",
            "correct": "debit",
            "steps": [
                "Bank is an Asset account.",
                "Assets increase on the **Debit (Dr)** side and decrease on the **Credit (Cr)** side.",
                "Answer: **Debit**"
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

    # 9. Business Studies (Gr 10-12)
    elif subject_id == "business_studies":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Business Studies",
            "topic": "Business Environments",
            "subtopic": "SWOT Analysis",
            "question": "In a SWOT analysis, which two elements analyze the INTERNAL environment of the business (controllable factors)?",
            "correct": "strengths and weaknesses",
            "steps": [
                "SWOT stands for Strengths, Weaknesses, Opportunities, Threats.",
                "Internal environment (controllable): **Strengths and Weaknesses**.",
                "External environment (macro/market): **Opportunities and Threats**."
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

    # 10. Economics (Gr 10-12)
    elif subject_id == "economics":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Economics",
            "topic": "Markets & Equilibrium",
            "subtopic": "Supply and Demand",
            "question": "When the quantity demanded equals the quantity supplied in a free market, what is this balanced state called?",
            "correct": "equilibrium",
            "steps": [
                "Market Equilibrium occurs where the demand curve intersects the supply curve.",
                "At this point, market price clears without surplus or shortage.",
                "Answer: **Equilibrium**"
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

    # 11. Geography (Gr 10-12)
    elif subject_id == "geography":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Geography",
            "topic": "Climatology & Weather",
            "subtopic": "Synoptic Charts",
            "question": "On a South African synoptic weather chart, what do the lines that join places of equal atmospheric pressure represent?",
            "correct": "isobars",
            "steps": [
                "Lines of equal atmospheric pressure are called **isobars**.",
                "They are measured in hectopascals (hPa).",
                "Answer: **Isobars**"
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

    # 12. History (Gr 10-12)
    elif subject_id == "history":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "History",
            "topic": "Cold War & Global Conflict",
            "subtopic": "Superpower Ideologies",
            "question": "During the Cold War (1945-1989), which two opposing economic and political ideologies were championed by the USA and the Soviet Union (USSR)?",
            "correct": "capitalism and communism",
            "steps": [
                "The USA led the Western bloc promoting democratic **capitalism** and free enterprise.",
                "The Soviet Union (USSR) promoted Marxist-Leninist **communism** and state control.",
                "Answer: **Capitalism and Communism**"
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

    # 13. Mathematical Literacy (Gr 10-12)
    elif subject_id == "maths_lit":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Mathematical Literacy",
            "topic": "Municipal Tariffs",
            "subtopic": "Stepped Water Tariffs",
            "question": "A municipality charges R15 per kL for the first 10 kL of water (Block 1), and R25 per kL for every kL thereafter (Block 2). Calculate the total cost for using 14 kL of water (in Rands).",
            "correct": "250",
            "steps": [
                "Block 1 (first 10 kL): 10 kL * R15 = R150",
                "Block 2 (remaining 4 kL): 4 kL * R25 = R100",
                "Total Cost = R150 + R100 = **R250**"
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

    # 14. English (Gr 8-12)
    elif subject_id == "english":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "English",
            "topic": "Figures of Speech",
            "subtopic": "Personification & Metaphor",
            "question": "Identify the figure of speech used in the line: 'The angry thunderstorm shouted across the dark sky and slammed against the windows.'",
            "correct": "personification",
            "steps": [
                "The thunderstorm is given human emotions and actions: 'angry', 'shouted', 'slammed'.",
                "Attributing human emotions or behaviors to non-human elements is **personification**."
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

    # 15. Life Orientation (Gr 8-12)
    elif subject_id == "life_orientation":
        return {
            "id": q_id,
            "grade": grade,
            "subject": "Life Orientation",
            "topic": "Goal Setting & SMART Principles",
            "subtopic": "SMART Framework",
            "question": "In the SMART goal-setting framework, what does the letter 'M' stand for?",
            "correct": "measurable",
            "steps": [
                "S = Specific",
                "M = **Measurable** (must have numbers, criteria, or milestones to track progress)",
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
        "id": q_id,
        "grade": grade,
        "subject": "General",
        "topic": active_topic,
        "subtopic": "Practice Exercise",
        "question": f"Review question for Grade {grade} on {active_topic}: What is 12 x 12?",
        "correct": "144",
        "steps": ["Calculate 12 x 12 = 144."],
        "diagram": "",
        "diagram_data": {},
        "hints": {"tiktok": "Basic multiplication! 12 times 12!", "casual": "Multiply 12 by 12.", "formal": "Compute the product."},
        "cheers": {"tiktok": "Locked in! 🔒", "casual": "Sharp! 🔥", "formal": "Correct."}
    }

# ---------------------------------------------------------
# 6. STREAMLIT USER INTERFACE & REACTIVE STATE SYNC
# ---------------------------------------------------------
def main():
    st.set_page_config(
        page_title="LockIn - South African CAPS Study Coach (Gr 8-12)",
        page_icon="🔒",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_db()

    if "current_q" not in st.session_state:
        st.session_state["current_q"] = None
    if "feedback" not in st.session_state:
        st.session_state["feedback"] = None
    if "last_selection_sig" not in st.session_state:
        st.session_state["last_selection_sig"] = ""

    curr_streak, best_streak, last_active = get_streak_info()

    # ------------------ SIDEBAR CONTROLS ------------------
    with st.sidebar:
        st.title("ZA LockIn Coach")
        st.caption("CAPS Study & Revision Engine")

        theme_choice = st.selectbox(
            "🎨 Aesthetic Theme:",
            options=list(AESTHETICS.keys()),
            format_func=lambda x: AESTHETICS[x]["name"]
        )
        inject_theme_css(theme_choice)

        tone_mode = st.radio(
    "🗣️ Study Tone:",
    options=["tiktok", "casual", "jjk", "formal"],
    format_func=lambda x: {
        "tiktok": "📱 TikTok Slang",
        "casual": "ZA Casual Lekker",
        "jjk": "⚔️ JJK ronin Mode",
        "formal": "🦅 Formal Academic"
    }[x],
    index=1
)

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
        if st.button("🗑️ Reset All Progress", use_container_width=True):
            reset_all_data()
            st.success("Database cleared!")
            st.rerun()

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
    tab_practice, tab_notes, tab_exam, tab_flashcards, tab_planner, tab_dashboard, tab_info = st.tabs([
        "📝 Practice Questions",
        "📖 Study Notes",
        "⏰ Timed CAPS Exam",
        "🃏 Flashcards Deck",
        "📅 Weekly Study Planner",
        "🏆 Badges & Analytics",
        "ℹ️ CAPS Curriculum Guide"
    ])

    # ==================== TAB 1: PRACTICE ====================
    with tab_practice:
        st.markdown(f"### **{subj_meta['icon']} {subj_meta['name']} — Grade {grade}**")
        st.info(f"**Topic:** {q['topic']} • *Subtopic:* {q['subtopic']}")
        st.markdown(f"#### {q['question']}")

        if q.get("math_expression"):
            st.caption("✍️ **Written Textbook Mathematical Notation:**")
            st.latex(q["math_expression"])

        if q.get("diagram"):
            svg_html = render_diagram_svg(q["diagram"], q.get("diagram_data", {}))
            if svg_html:
                st.markdown(svg_html, unsafe_allow_html=True)

        with st.expander(f"💡 Need a Hint? ({tone_mode.capitalize()} Mode)"):
            st.write(q["hints"].get(tone_mode, q["hints"]["casual"]))

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
                record_practice_attempt(grade, subj_meta["name"], q["topic"], q["subtopic"], q["question"], user_ans, q["correct"], is_corr, tone_mode)

                st.session_state["feedback"] = {
                    "is_correct": is_corr,
                    "user_ans": user_ans,
                    "correct_ans": q["correct"],
                    "steps": q["steps"],
                    "cheer": q["cheers"].get(tone_mode, q["cheers"]["casual"])
                }

        if st.session_state.get("feedback"):
            fb = st.session_state["feedback"]
            if fb["is_correct"]:
                st.success(f"🎉 **{fb['cheer']}** Correct Answer: **{fb['correct_ans']}**")
            else:
                st.error(f"❌ **Not quite!** Your Answer: **{fb['user_ans']}** | Correct Answer: **{fb['correct_ans']}**")

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

    # ==================== TAB 2: NOTES ====================
    with tab_notes:
        st.subheader("📖 CAPS Study & Revision Notes")
        st.caption("Official CAPS summaries, definitions, formulas, and exam traps.")

        notes_tone_choice = st.radio(
            "🗣️ Select Notes Tone Alignment:",
            ["📱 TikTok Slang Mode (Gen Z)", "☕ ZA Casual Lekker", "⚔️ JJK Ronin Mode", "🎓 Formal Academic (DBE Standard)"],
            horizontal=True,
            index=0 if tone_mode == "tiktok" else (1 if tone_mode == "casual" else (2 if tone_mode == "jjk" else 3)),
            key="notes_tone_radio"
        )
        notes_tone_key = "tiktok" if "TikTok" in notes_tone_choice else ("casual" if "Casual" in notes_tone_choice else ("jjk" if "JJK" in notes_tone_choice else "formal"))

        notes_subject_id = subject_id
        notes_grade = grade

        # === JJK RONIN MODE ===
        if notes_tone_key == "jjk":
            jjk_notes = get_jjk_notes_for_subject(notes_subject_id)
            if jjk_notes:
                st.subheader(f"⚔️ {SUBJECTS[notes_subject_id]['icon']} {jjk_notes['subject_name']} — JJK RONIN CURSED NOTES")
                st.caption(f"**Domain Expansion:** {jjk_notes['domain_expansion']} • **Curse Level:** {jjk_notes['curse_level']}")
                st.markdown(f"### ⚔️ {jjk_notes['opening']}")
                st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🎯 Sure-Hit Technique")
                    st.info(jjk_notes['sure_hit'])
                    st.markdown("#### 🔄 Reverse Cursed Technique")
                    st.info(jjk_notes['reverse_cursed_technique'])
                with col2:
                    st.markdown("#### ⚡ Black Flash")
                    st.success(jjk_notes['black_flash'])
                    st.markdown("#### 📜 Binding Vow")
                    st.warning(jjk_notes['binding_vow'])

                st.markdown("#### 🗡️ Your Cursed Tools")
                for tool in jjk_notes['cursed_tools']:
                    st.markdown(f"- {tool}")

                st.divider()
                st.markdown(f"### 📖 {jjk_notes['final_word']}")
            else:
                st.warning(f"JJK notes for {SUBJECTS[notes_subject_id]['name']} coming soon, ronin.")

            # === ALSO SHOW STANDARD CAPS CONTENT BELOW JJK VIBE ===
            st.divider()
            st.markdown("### 📖 The Actual Study Content (DBE Standard)")
            st.caption("Vibes are cool, but formulas win marks. Here's the real stuff:")

            subj_notes_jjk = CAPS_STUDY_NOTES.get(notes_subject_id, None)
            if subj_notes_jjk:
                matching_ch_jjk = [
                    ch for ch in subj_notes_jjk.get("chapters", [])
                    if notes_grade in ch.get("grades", [])
                ]
                for ch in matching_ch_jjk:
                    with st.expander(f"📚 {ch['title']}", expanded=True):
                        st.markdown(f"**📌 Overview:** {ch['summary']}")

                        if ch.get("definitions"):
                            st.markdown("#### 📖 Key Definitions")
                            for term, defn in ch["definitions"]:
                                st.markdown(f"- **{term}**: {defn}")

                        if ch.get("formulas"):
                            st.markdown("#### 📐 Formulas & Frameworks")
                            for f_name, f_eq, f_note in ch["formulas"]:
                                st.markdown(f"- **{f_name}**: `{f_eq}`")

                        if ch.get("worked_example"):
                            ex = ch["worked_example"]
                            st.markdown("#### 💡 Worked Example")
                            st.info(f"**Problem:** {ex['problem']}")
                            for step in ex["steps"]:
                                st.markdown(f"- {step}")
                            st.success(f"**Final Answer:** {ex['answer']}")

                        col_pj, col_tj = st.columns(2)
                        with col_pj:
                            if ch.get("pitfalls"):
                                st.markdown("#### ⚠️ Pitfalls")
                                for pit in ch["pitfalls"]:
                                    st.markdown(f"- ❌ {pit}")
                        with col_tj:
                            if ch.get("tips"):
                                st.markdown("#### 🎯 Exam Tips")
                                for tip in ch["tips"]:
                                    st.markdown(f"- ✨ {tip}")
        # === STANDARD CAPS NOTES ===
        else:
            subj_notes = CAPS_STUDY_NOTES.get(notes_subject_id, None)
            if not subj_notes:
                st.info(f"No revision notes available for {SUBJECTS[notes_subject_id]['name']} yet.")
            else:
                matching_chapters = [
                    ch for ch in subj_notes.get("chapters", [])
                    if notes_grade in ch.get("grades", [])
                ]

                if not matching_chapters:
                    st.warning(f"No notes for Grade {notes_grade}. Available grades:")
                    for ch in subj_notes.get("chapters", []):
                        st.markdown(f"- **{ch['title']}** (Grades {', '.join(str(g) for g in ch['grades'])})")
                else:
                    for ch in matching_chapters:
                        with st.expander(f"📚 {ch['title']} (Grades {', '.join(str(g) for g in ch['grades'])})", expanded=True):
                            tone_data = adapt_chapter_to_tone(ch['title'], ch['summary'], notes_tone_key, subj_notes['subject_name'])
                            st.markdown(f"### {tone_data['hook']}")
                            st.caption(tone_data['badge'])
                            st.markdown(tone_data['summary'])

                            if ch.get("definitions"):
                                st.markdown("#### 📖 Key Definitions")
                                for term, defn in ch["definitions"]:
                                    st.markdown(f"- **{term}**: {defn}")

                            if ch.get("formulas"):
                                st.markdown("#### 📐 Formulas & Frameworks")
                                for f_name, f_eq, f_note in ch["formulas"]:
                                    st.markdown(f"- **{f_name}**: `{f_eq}`")

                            if ch.get("worked_example"):
                                ex = ch["worked_example"]
                                st.markdown("#### 💡 Worked Example")
                                st.info(f"**Problem:** {ex['problem']}")
                                for step in ex["steps"]:
                                    st.markdown(f"- {step}")
                                st.success(f"**Final Answer:** {ex['answer']}")

                            col_p, col_t = st.columns(2)
                            with col_p:
                                if ch.get("pitfalls"):
                                    st.markdown("#### ⚠️ Common Pitfalls")
                                    for pit in ch["pitfalls"]:
                                        st.markdown(f"- ❌ {pit}")
                            with col_t:
                                if ch.get("tips"):
                                    st.markdown("#### 🎯 Exam Tips")
                                    for tip in ch["tips"]:
                                        st.markdown(f"- ✨ {tip}")
    # ==================== TAB 3: EXAM ====================
        with tab_exam:
          st.subheader("⏱️ Official CAPS Timed Exam Simulation")
        st.markdown(f"**10 Questions • {subj_meta['name']} • Grade {grade}**")

        if "exam_state" not in st.session_state:
            st.session_state["exam_state"] = None

        if st.session_state["exam_state"] is None:
            if st.button("🚀 Start 10-Question Timed Exam", type="primary", use_container_width=True):
                topics_list = subj_meta["topics"].get(grade, ["General"])
                exam_questions = []
                for i in range(10):
                    t = topics_list[i % len(topics_list)]
                    exam_questions.append(generate_lockin_question(subject_id, grade, t, "formal"))
                st.session_state["exam_state"] = {
                    "questions": exam_questions,
                    "answers": [""] * 10,
                    "submitted": False,
                    "score": 0,
                }
                st.rerun()
        else:
            exam = st.session_state["exam_state"]
            if not exam["submitted"]:
                st.info("🕒 **Time Allocation:** 15 Minutes recommended.")
                with st.form("exam_form"):
                    for idx, eq in enumerate(exam["questions"]):
                        st.markdown(f"**Question {idx + 1} ({eq['topic']}):** {eq['question']}")
                        if eq.get("math_expression"):
                            st.latex(eq["math_expression"])
                        exam["answers"][idx] = st.text_input(f"Your Answer for Q{idx + 1}:", value=exam["answers"][idx], key=f"exam_ans_{idx}")
                        st.write("")

                    submit_exam = st.form_submit_button("🏁 Submit Completed Exam", type="primary", use_container_width=True)
                    if submit_exam:
                        score = 0
                        for idx, eq in enumerate(exam["questions"]):
                            u = exam["answers"][idx].strip().lower()
                            c = eq["correct"].strip().lower()
                            if u == c or (u and u in c):
                                score += 1
                        exam["score"] = score
                        exam["submitted"] = True
                        if (score / 10.0) >= 0.8:
                            st.session_state["has_level_7"] = True
                        st.rerun()
            else:
                pct = int((exam["score"] / 10) * 100)
                level = 7 if pct >= 80 else (6 if pct >= 70 else (5 if pct >= 60 else (4 if pct >= 50 else (3 if pct >= 40 else (2 if pct >= 30 else 1)))))
                level_desc = {
                    7: "Outstanding Achievement (80–100%)",
                    6: "Meritorious Achievement (70–79%)",
                    5: "Substantial Achievement (60–69%)",
                    4: "Adequate Achievement (50–59%)",
                    3: "Moderate Achievement (40–49%)",
                    2: "Elementary Achievement (30–39%)",
                    1: "Not Achieved (0–29%)"
                }[level]

                st.markdown(f"### **Exam Result: {exam['score']} / 10 ({pct}%)**")
                st.markdown(f"#### Official CAPS Rating: **Level {level} — {level_desc}**")

                if pct >= 80:
                    st.success("🏆 **Distinction Standard!**")
                elif pct >= 50:
                    st.info("✅ **Passing standard met!**")
                else:
                    st.warning("⚠️ **Focus Required.**")

                if st.button("🔄 Take Another Exam", type="secondary"):
                    st.session_state["exam_state"] = None
                    st.rerun()

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

        df_attempts = get_attempts_df()
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
        df = get_attempts_df()
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

    # ==================== TAB 7: INFO ====================
    with tab_info:
        st.subheader("ℹ️ Official CAPS Curriculum Coverage Guide")
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
        jjk_sum = f"Listen, ronin. This chapter is your next mission. {summary} The examiner's cursed energy is strong, but your technique is stronger — IF you master the fundamentals. Complete your Reverse Cursed Technique by practising until you can do it without thinking."
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
            "badge": "⚔️ JJK Ronin Mode",
            "summary": jjk_sum,
            "takeaways": [
                "⚔️ Mission 1: Master the fundamental technique before attempting complex missions.",
                "⚔️ Mission 2: Practice under pressure — the Shibuya Incident exam is coming.",
                "⚔️ Mission 3: Land Black Flash by locking in for 25 focused minutes a day."
            ],
            "pitfall": "💀 Cursed Spirit Alert: Sign errors, missing units, and skipped steps are ambushes. Do not fall for them.",
            "tip": "🚀 Ronin's Path: Do 3 practice questions in a row correctly to unlock Reverse Cursed Technique."
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








