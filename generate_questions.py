"""
Generate AI-powered practice questions for Grade 8 CAPS subjects.
Saves to ai_questions.json as {subject: {grade: {topic: [questions]}}}.
Safe to re-run — skips what's already done.
"""

import json
import os
import time
from groq import Groq

import os
from dotenv import load_dotenv
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===== WHAT TO GENERATE =====
TARGET_GRADE = 8
QUESTIONS_PER_TOPIC = 5  # 5 questions per topic per call

# Only Grade 8 subjects
SUBJECTS_AND_TOPICS = {
    "mathematics": [
        "Integers (Calculations & Signs)",
        "Common Fractions & Decimals",
        "Exponents & Powers",
        "Algebraic Expressions",
        "Geometry of Straight Lines",
        "Theorem of Pythagoras",
        "Perimeter & Area of 2D Shapes",
    ],
    "natural_sciences": [
        "Human Digestive System",
        "Plant & Animal Cells",
        "Photosynthesis & Respiration",
        "Atoms & Periodic Table",
        "Particle Model of Matter",
        "Electric Circuits (Series & Parallel)",
    ],
    "ems": [
        "The Accounting Equation (A = O + L)",
        "Cash Receipts Journal (CRJ)",
        "Financial Literacy & Personal Budget",
        "Factors of Production",
        "Forms of Ownership",
    ],
    "social_sciences": [
        "Topographic Maps & 1:50 000 Scale",
        "Climate Regions of the World",
        "Settlement Patterns in South Africa",
        "Mineral Revolution in South Africa",
        "World War I Causes",
    ],
    "technology": [
        "Structural Analysis & Triangulation",
        "Class 1, 2, 3 Levers & Mechanical Advantage",
        "Gear Trains & Velocity Ratios",
        "Electrical Components & Logic",
    ],
    "english": [
        "Figures of Speech (Metaphor, Simile, Personification)",
        "Active and Passive Voice",
        "Direct and Indirect Speech",
        "Parts of Speech & Punctuation",
    ],
    "life_orientation": [
        "Development of the Self & Self-Concept",
        "Healthy Lifestyle & Substance Abuse",
        "Human Rights & Social Justice in SA",
        "Career Choices & Subjects",
    ],
}

SUBJECT_DISPLAY = {
    "mathematics": "Mathematics",
    "natural_sciences": "Natural Sciences",
    "ems": "Economic & Management Sciences",
    "social_sciences": "Social Sciences",
    "technology": "Technology",
    "english": "English",
    "life_orientation": "Life Orientation",
}


def build_prompt(subject_id, topic):
    subject_display = SUBJECT_DISPLAY[subject_id]
    return f"""You are an expert South African CAPS curriculum teacher.
Generate exactly {QUESTIONS_PER_TOPIC} practice questions for Grade {TARGET_GRADE} {subject_display} on the topic: "{topic}".

Return ONLY valid JSON in this exact format:
{{
  "questions": [
    {{
      "subtopic": "A specific subtopic name",
      "question": "The full question text",
      "correct": "The correct answer (short, e.g. '5' or 'stomach' or 'steep')",
      "steps": ["Step 1 explanation", "Step 2 explanation", "Step 3 explanation"],
      "hints": {{
        "tiktok": "A Gen Z slang hint using 'no cap', 'lock in', 'bro' etc",
        "casual": "A friendly South African casual hint",
        "jjk": "A Jujutsu Kaisen narrator hint using 'ronin', 'cursed energy' etc",
        "formal": "A formal academic DBE-style hint"
      }},
      "cheers": {{
        "tiktok": "A hype Gen Z celebration",
        "casual": "A warm South African celebration",
        "jjk": "A JJK-style compliment",
        "formal": "A brief formal acknowledgement"
      }}
    }}
  ]
}}

Rules:
- Answers must be SHORT and easy to type (numbers, single words, short phrases).
- No multiple choice. The answer is free text.
- Use South African context (rands, local places, DBE terminology).
- Keep the hints and cheers short (1-2 sentences each).
- Return ONLY the JSON object, no markdown fences."""


def generate_questions_for_topic(subject_id, topic, max_retries=5):
    subject_display = SUBJECT_DISPLAY[subject_id]
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   📚 {subject_display} → {topic[:40]} (try {attempt})...", end=" ", flush=True)
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": build_prompt(subject_id, topic)}],
                response_format={"type": "json_object"},
                temperature=0.85,
            )
            data = json.loads(response.choices[0].message.content)
            print("✅")
            return data.get("questions", [])
        except Exception as e:
            print(f"❌ ({type(e).__name__})")
            if attempt < max_retries:
                wait = 70
                print(f"      ⏳ Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"      💀 Giving up on this topic.")
                return []


def load_existing():
    if os.path.exists("ai_questions.json"):
        with open("ai_questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(data):
    with open("ai_questions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    all_questions = load_existing()

    total_topics = sum(len(topics) for topics in SUBJECTS_AND_TOPICS.values())
    print(f"🎯 Target: {total_topics} topics × {QUESTIONS_PER_TOPIC} questions = {total_topics * QUESTIONS_PER_TOPIC} questions\n")

    for subject_id, topics in SUBJECTS_AND_TOPICS.items():
        if subject_id not in all_questions:
            all_questions[subject_id] = {}
        if str(TARGET_GRADE) not in all_questions[subject_id]:
            all_questions[subject_id][str(TARGET_GRADE)] = {}

        for topic in topics:
            if topic in all_questions[subject_id][str(TARGET_GRADE)]:
                print(f"   ⏭️  Skipping (already done): {subject_id} → {topic[:40]}")
                continue

            questions = generate_questions_for_topic(subject_id, topic)

            # Add metadata to each question
            for q in questions:
                q["grade"] = TARGET_GRADE
                q["subject"] = SUBJECT_DISPLAY[subject_id]
                q["topic"] = topic

            all_questions[subject_id][str(TARGET_GRADE)][topic] = questions
            save_progress(all_questions)
            time.sleep(70)  # Stay under rate limit

    # Summary
    print("\n" + "=" * 50)
    total = sum(
        len(qs)
        for subj in all_questions.values()
        for grd in subj.values()
        for qs in grd.values()
    )
    print(f"✅ Total questions generated: {total}")
    print("📁 Saved to: ai_questions.json")
    print("=" * 50)


if __name__ == "__main__":
    main()