"""Debug script: check kyun questions reject ho rahe hain."""
from parser_utils import clean_text, parse_questions

# Paste yahan apna original text (jo 50 questions wala tha)
RAW_TEXT = """Paste apna text yahan..."""

text = clean_text(RAW_TEXT or "")
total_lines = [l for l in text.splitlines() if l.strip()]
parsed = parse_questions(text)

print(f"Total non-empty lines: {len(total_lines)}")
print(f"Parsed questions: {len(parsed)}")
print(f"Rejected: {len(total_lines) - len(parsed)}")
print()

# Rejected lines dikhao
for i, line in enumerate(total_lines, 1):
    s = line.strip()
    if not s.startswith("Q:"):
        print(f"  [{i}] SKIP: 'Q:' se nahi shuru -> {s[:60]}")
        continue
    parts = [p.strip() for p in s[2:].split("|")]
    if len(parts) < 6:
        print(f"  [{i}] SKIP: sirf {len(parts)} parts (chahiye 6) -> {s[:60]}")
        continue
    qtext = clean_text(parts[0])
    opts = [p.strip() for p in parts[1:5]]
    if not qtext or any(not o for o in opts):
        print(f"  [{i}] SKIP: khali question ya option -> {s[:60]}")
        continue
    ans_raw = clean_text(parts[5]).replace("Ans:", "").replace("ANS:", "").strip().upper()
    import re
    m = re.search(r"[ABCD]", ans_raw)
    if not m:
        print(f"  [{i}] SKIP: answer mein A/B/C/D nahi -> {s[:60]}")
        continue
    print(f"  [{i}] OK -> {s[:60]}")