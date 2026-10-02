"""
Regenerate all CAPS notes in ALL 4 tones (tiktok, casual, jjk, formal).
Saves to ai_notes.json as {subject: {tone: notes}}.
Safe to re-run — it skips what's already done.
"""

import json
import os
import time
from groq import Groq

import os
from dotenv import load_dotenv
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))# 👈 PASTE YOUR KEY HERE

SUBJECTS_TO_GENERATE = [
    "mathematics", "natural_sciences", "ems", "social_sciences",
    "technology", "physical_sciences", "life_sciences", "accounting",
    "business_studies", "economics", "geography", "history",
    "maths_lit", "english", "life_orientation",
]

TONES = ["formal", "casual", "tiktok", "jjk"]

TONE_INSTRUCTIONS = {
   
    "tiktok": "Speak in pure Gen Z TikTok slang. Use: 'no cap', 'lock in', 'ate', 'sheesh', 'bro', 'bestie', 'main character energy', 'lil', 'fr fr', 'on god', 'W', 'L'. Be hype and fast. NEVER use South African slang or formal language — this is strictly Gen Z American influencer vibes.",
    "casual": "Speak like a friendly South African older sibling (boet or sister). Use words like 'eish', 'shame', 'lekker', 'sharp sharp', 'just now', 'howzit', 'ja nee', 'yoh'. Be warm and encouraging, like someone explaining over a braai. NEVER use American Gen Z slang like 'no cap', 'fire', 'ate', 'lock in' — that's a different mode.",
        "jjk": "Speak like a dramatic anime training-arc narrator hyping up a young hero. Use phrases like: 'Champion', 'Final Form', 'Peak Focus', 'Unlock your potential', 'Flow State', 'Power Up', 'Level Up', 'Master this technique', 'Your moment is now', 'Sharpen your blade', 'Surpass your limits'. Structure sentences like a shonen anime opening: 'This is the moment where you become unstoppable.' Be motivational and dramatic. NEVER use American Gen Z slang (no 'no cap', 'lock in', 'bro', 'bestie', 'fr fr', 'ate', 'sheesh', 'W', 'L'). NEVER use South African slang (no 'eish', 'lekker', 'sharp sharp', 'howzit'). NEVER use religious or occult language (no 'cursed', 'soul', 'vow', 'spirit', 'sacred'). Keep it clean, anime-hype, motivational, and dramatic.",
    "formal": "Use strict academic DBE-style formal language with precise CAPS terminology.",
} 

def build_prompt(subject_id, tone):
    subject_display = subject_id.replace("_", " ").title()
    tone_note = TONE_INSTRUCTIONS[tone]

    return f"""You are an expert South African CAPS curriculum teacher.
Generate detailed study notes for Grade 8 {subject_display} that follow the official CAPS curriculum.

**TONE REQUIREMENT:** {tone_note}

Return ONLY valid JSON with this exact structure:
{{
  "subject_name": "{subject_display}",
  "curriculum_overview": "A 2-sentence summary of what this subject covers",
  "tone": "{tone}",
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

Generate notes for 3 key chapters of Grade 8 {subject_display}.
Use South African context (rands, local places, DBE terminology).
Return ONLY the JSON object, no markdown fences, no extra text."""

def generate_notes(subject_id, tone, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   📚 {subject_id} [{tone}] (try {attempt})...", end=" ", flush=True)
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": build_prompt(subject_id, tone)}],
                response_format={"type": "json_object"},
                # Lower temperature on retries for more predictable JSON
                temperature=0.7 if attempt == 1 else 0.3,
            )
            notes = json.loads(response.choices[0].message.content)
            print("✅")
            return notes
        except Exception as e:
            print(f"❌ (try {attempt})")
            if attempt < max_retries:
                wait = 30  # Wait 30s to reset the rate limit
                print(f"      ⏳ Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                print(f"      💀 Gave up after {max_retries} tries: {type(e).__name__}")
                raise  # Re-raise so the outer loop catches it and continues


def load_existing():
    """Load existing file if it exists (for resuming)."""
    if os.path.exists("ai_notes.json"):
        with open("ai_notes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(data):
    """Save after every successful generation so we never lose progress."""
    with open("ai_notes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    # 1. Back up the old single-tone file just in case
    if os.path.exists("ai_notes.json") and not os.path.exists("ai_notes_backup.json"):
        os.rename("ai_notes.json", "ai_notes_backup.json")
        print("💾 Backed up old file to ai_notes_backup.json\n")

    # 2. Load existing (resume mode)
    all_notes = load_existing()

    total_jobs = len(SUBJECTS_TO_GENERATE) * len(TONES)
    completed = sum(
        1 for s in SUBJECTS_TO_GENERATE
        for t in TONES
        if s in all_notes and t in all_notes[s]
    )
    print(f"🎯 Total jobs: {total_jobs} | Already done: {completed}\n")

    # 3. Generate every subject × tone combo
    for subject in SUBJECTS_TO_GENERATE:
        if subject not in all_notes:
            all_notes[subject] = {}

        for tone in TONES:
            if tone in all_notes[subject]:
                continue  # Already done, skip

            try:
                all_notes[subject][tone] = generate_notes(subject, tone)
                save_progress(all_notes)  # Save after every success
                time.sleep(20)
            except Exception as e:
                print(f"❌")
                print(f"      {type(e).__name__}: {e}")
                time.sleep(3)

    # 4. Final summary
    print("\n" + "=" * 50)
    final_count = sum(1 for s in all_notes for t in all_notes[s])
    print(f"✅ Total note sets: {final_count} / {total_jobs}")
    print("📁 Saved to: ai_notes.json")
    print("=" * 50)


if __name__ == "__main__":
    main()