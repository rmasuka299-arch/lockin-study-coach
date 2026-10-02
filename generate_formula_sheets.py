"""
Generate formula sheets, glossaries, and memory hooks per subject.
Saves to ai_formula_sheets.json.
"""

import json
import os
import time
from groq import Groq

import os
from dotenv import load_dotenv
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SUBJECTS_TO_GENERATE = [
    "mathematics", "natural_sciences", "ems", "social_sciences",
    "technology", "physical_sciences", "life_sciences", "accounting",
    "business_studies", "economics", "geography", "history",
    "maths_lit", "english", "life_orientation",
]

SUBJECT_DISPLAY = {
    "mathematics": "Mathematics",
    "natural_sciences": "Natural Sciences",
    "ems": "Economic & Management Sciences",
    "social_sciences": "Social Sciences",
    "technology": "Technology",
    "physical_sciences": "Physical Sciences",
    "life_sciences": "Life Sciences",
    "accounting": "Accounting",
    "business_studies": "Business Studies",
    "economics": "Economics",
    "geography": "Geography",
    "history": "History",
    "maths_lit": "Mathematical Literacy",
    "english": "English",
    "life_orientation": "Life Orientation",
}


def build_prompt(subject_id):
    subject = SUBJECT_DISPLAY[subject_id]
    return f"""You are a CAPS curriculum expert. Generate a compact study reference sheet for Grade 8 {subject}.

Return ONLY valid JSON:
{{
  "subject_name": "{subject}",
  "formulas": [
    {{"name": "Formula Name", "formula": "the formula", "use_when": "when to use it"}}
  ],
  "glossary": [
    {{"term": "Term", "definition": "Simple definition with SA context if possible"}}
  ],
  "memory_hooks": [
    {{"concept": "Concept", "hook": "A mnemonic, rhyme, or memory trick"}}
  ]
}}

Rules:
- 6-10 formulas (or key rules if subject has no formulas)
- 8-12 glossary terms
- 4-6 memory hooks
- South African context where possible
- Return ONLY the JSON object, no markdown"""


def generate(subject_id, max_retries=3):
    subject = SUBJECT_DISPLAY[subject_id]
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   📐 {subject} (try {attempt})...", end=" ", flush=True)
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": build_prompt(subject_id)}],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            data = json.loads(response.choices[0].message.content)
            print("✅")
            return data
        except Exception as e:
            print(f"❌ ({type(e).__name__})")
            if attempt < max_retries:
                time.sleep(30)
            else:
                print(f"      💀 Gave up on {subject}")
                return None


def main():
    existing = {}
    if os.path.exists("ai_formula_sheets.json"):
        with open("ai_formula_sheets.json", "r", encoding="utf-8") as f:
            existing = json.load(f)

    for subject_id in SUBJECTS_TO_GENERATE:
        if subject_id in existing:
            print(f"   ⏭️  Skipping (already done): {subject_id}")
            continue

        result = generate(subject_id)
        if result:
            existing[subject_id] = result
            with open("ai_formula_sheets.json", "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            time.sleep(20)

    print("\n" + "=" * 50)
    print(f"✅ Total subjects: {len(existing)} / {len(SUBJECTS_TO_GENERATE)}")
    print("📁 Saved to: ai_formula_sheets.json")
    print("=" * 50)


if __name__ == "__main__":
    main()