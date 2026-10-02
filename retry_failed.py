"""
Retry only the subjects that failed in the last run.
Loads ai_notes.json, generates only the missing ones, and saves back.
"""

import json
import time
from groq import  Groq

import os
from dotenv import load_dotenv
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 👇 Add any subjects that failed here
FAILED_SUBJECTS = [
    "mathematics"
]

PROMPT_TEMPLATE = """You are an expert South African CAPS curriculum teacher.
Generate detailed study notes for Grade 8 {subject} that follow the official CAPS curriculum.

Return ONLY valid JSON with this exact structure:
{{
  "subject_name": "The subject's display name",
  "curriculum_overview": "A 2-sentence summary of what this subject covers",
  "chapters": [
    {{
      "title": "Chapter title",
      "grades": [8],
      "summary": "A detailed 3-4 sentence summary of this chapter",
      "definitions": [["Term 1", "Definition 1"], ["Term 2", "Definition 2"]],
      "formulas": [["Formula Name", "The formula", "When to use it"]],
      "worked_example": {{
        "problem": "A sample exam-style problem",
        "steps": ["Step 1...", "Step 2...", "Step 3..."],
        "answer": "The final answer"
      }},
      "pitfalls": ["Common mistake 1", "Common mistake 2"],
      "tips": ["Exam tip 1", "Exam tip 2"]
    }}
  ]
}}

Generate notes for 3 key chapters of Grade 8 {subject}.
Use South African context (rands, local places, DBE terminology).
Return ONLY the JSON object, no markdown fences, no extra text."""


def generate_notes_for_subject(subject_id):
    print(f"📚 Retrying: {subject_id}...")
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(subject=subject_id.replace("_", " "))}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    raw_text = response.choices[0].message.content
    return json.loads(raw_text)


def main():
    # 1. Load what we already have
    with open("ai_notes.json", "r", encoding="utf-8") as f:
        all_notes = json.load(f)

    print(f"✅ Already have {len(all_notes)} subjects: {list(all_notes.keys())}")

    # 2. Retry only the failures
    for subject in FAILED_SUBJECTS:
        try:
            all_notes[subject] = generate_notes_for_subject(subject)
            print(f"   ✅ Done: {subject}")
            time.sleep(1)
        except Exception as e:
            print(f"   ❌ Still failed: {subject}")
            print(f"   🔍 {type(e).__name__}: {e}")
            time.sleep(2)

    # 3. Save back
    with open("ai_notes.json", "w", encoding="utf-8") as f:
        json.dump(all_notes, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"✅ Total subjects now: {len(all_notes)} / 15")
    print("📁 Saved to: ai_notes.json")
    print("=" * 50)


if __name__ == "__main__":
    main()