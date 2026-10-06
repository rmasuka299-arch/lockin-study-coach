"""
One-time script to generate CAPS study notes for all subjects using Groq.
Run this ONCE. It saves the output to ai_notes.json.
"""

import json
import time
from groq import Groq

import os
import json
from groq import Groq
from dotenv import load_dotenv  # 🌟 Added to handle local environment configurations securely

# Load the local secret key variables from your hidden .env file
load_dotenv()

# Extract the key cleanly using python's system library
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("⚠️ GROQ_API_KEY could not be found! Double check your .env file is formatted correctly.")
    exit()

client = Groq(api_key=api_key)


# Subjects to generate notes for (matching your SUBJECTS dictionary keys)
SUBJECTS_TO_GENERATE = [
    "mathematics",
    "natural_sciences",
    "ems",
    "social_sciences",
    "technology",
    "physical_sciences",
    "life_sciences",
    "accounting",
    "business_studies",
    "economics",
    "geography",
    "history",
    "maths_lit",
    "english",
    "life_orientation",
]

# The prompt we send to the AI for each subject
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
    """Call Groq to generate notes for one subject."""
    print(f"📚 Generating notes for: {subject_id}...")

    response = client.chat.completions.create(
            model="openai/gpt-oss-120b",  # Current Groq production model   
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(subject=subject_id.replace("_", " "))}
        ],
        response_format={"type": "json_object"},  # Force valid JSON output[reference:3]
        temperature=0.7,
    )

    raw_text = response.choices[0].message.content
    return json.loads(raw_text)


def main():
    all_notes = {}
    failed = []

    for subject in SUBJECTS_TO_GENERATE:
        try:
            all_notes[subject] = generate_notes_for_subject(subject)
            print(f"   ✅ Done: {subject}")
            time.sleep(1)  # Be polite to the API
        except Exception as e:
            print(f"   ❌ Failed for {subject}")
            print(f"   🔍 ERROR TYPE: {type(e).__name__}")
            print(f"   🔍 ERROR MSG : {e}")
            print()
            failed.append(subject)
            time.sleep(2)
    with open("ai_notes.json", "w", encoding="utf-8") as f:
        json.dump(all_notes, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"✅ Generated notes for {len(all_notes)} subjects")
    if failed:
        print(f"❌ Failed for: {failed}")
    print("📁 Saved to: ai_notes.json")
    print("=" * 50)


if __name__ == "__main__":
    main()