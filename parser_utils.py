"""Question parsing - multi-line text format + PDF text extract.

Format (har question 4-6 line mein):
Q: Sawal kya hai?
A) Option 1
B) Option 2
C) Option 3
D) Option 4
Ans: B
Exp: explanation (optional)

Agla sawal naye Q: se shuru karein.
"""
import logging
import re

logger = logging.getLogger(__name__)

Q_FMT = ("Q: Sawal kya hai?\n"
         "A) Option 1\n"
         "B) Option 2\n"
         "C) Option 3\n"
         "D) Option 4\n"
         "Ans: B\n"
         "Exp: explanation (optional)\n"
         "\n"
         "Agla sawal naye Q: se shuru karein.")

ANSWER_MAP = {"A": 0, "B": 1, "C": 2, "D": 3}
_WS_RE = re.compile(r"[ \t\u00a0]+")
_MULTI_NL = re.compile(r"\n{3,}")


def clean_text(s: str) -> str:
    """PDF/typing se aaya kachra saaf karo: null-bytes, control chars, extra space."""
    if not s:
        return ""
    # null bytes + common control chars (newline/tab rakho)
    s = s.replace("\x00", " ").replace("\u0000", " ")
    s = "".join(ch for ch in s if ch in ("\n", "\t") or ord(ch) >= 32 or ch in ("’", "‘"))
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # har line ke andar extra spaces samato
    lines = [_WS_RE.sub(" ", ln).strip() for ln in s.split("\n")]
    s = "\n".join(lines)
    s = _MULTI_NL.sub("\n\n", s)
    return s.strip()


def _clean_opt(s: str) -> str:
    s = clean_text(s)
    # "A) Delhi" / "A. Delhi" / "1. Delhi" jaise prefix hatao
    s = re.sub(r"^[A-Da-d1-4][\.\)\:\-]\s+", "", s).strip()
    return s


def parse_questions(text):
    """Multi-line format parser.

    Har question is format mein ho sakta hai:
        Q: Sawal kya hai?
        A) Option 1
        B) Option 2
        C) Option 3
        D) Option 4
        Ans: B
        Exp: explanation (optional)

    Agla sawal naye Q: se shuru hona chahiye. Blank line optional hai.
    Purana single-line format (Q: ... | A | B | C | D | Ans: B) bhi support hoga.
    """
    text = clean_text(text or "")
    qs = []
    lines = text.split("\n")

    # ---- Step 1: lines ko question-blocks mein todo (har Q: se naya block shuru) ----
    blocks = []
    current_block = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("Q:"):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        else:
            if current_block:          # sirf us line ko lojo jo Q: ke baad aayi ho
                current_block.append(line)
    if current_block:
        blocks.append(current_block)

    # ---- Agar koi Q: line nahi mili, to purana single-line format try karein ----
    if not blocks:
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("Q:"):
                continue
            parts = [p.strip() for p in line[2:].split("|")]
            if len(parts) < 6:
                continue
            qtext = clean_text(parts[0])
            opts = [_clean_opt(p) for p in parts[1:5]]
            if not qtext or any(not o for o in opts):
                continue
            ans_raw = clean_text(parts[5]).replace("Ans:", "").replace("ANS:", "").strip().upper()
            m = re.search(r"[ABCD]", ans_raw)
            if not m:
                continue
            ans_letter = m.group(0).upper()
            if ans_letter not in ANSWER_MAP:
                continue
            exp = ""
            if len(parts) > 6 and parts[6].lower().startswith("exp:"):
                exp = clean_text(parts[6][4:])
            if len(qtext) > 300:
                qtext = qtext[:297] + "..."
            opts = [o[:100] if len(o) > 100 else o for o in opts]
            if len(exp) > 200:
                exp = exp[:197] + "..."
            qs.append({
                "question": qtext,
                "options": opts,
                "correct": ANSWER_MAP[ans_letter],
                "explanation": exp,
            })
        return qs

    # ---- Har block ko parse karein ----
    for block in blocks:
        qtext = ""
        opts = ["", "", "", ""]
        ans_raw = ""
        exp = ""

        for line in block:
            line = line.strip()
            if not line:
                continue
            upper = line.upper()

            # Question line
            if upper.startswith("Q:"):
                qtext = clean_text(line[2:].strip())
            # Option lines: A), B), C), D)  ya  A., B., C., D.  ya  A: B:
            elif re.match(r"^[A-Da-d1-4][\.\\)\\:\-]\s+", line):
                opt_text = re.sub(r"^[A-Da-d1-4][\.\\)\\:\-]\s+", "", line).strip()
                prefix = line[0].upper()
                if prefix == "A":
                    opts[0] = opt_text
                elif prefix == "B":
                    opts[1] = opt_text
                elif prefix == "C":
                    opts[2] = opt_text
                elif prefix == "D":
                    opts[3] = opt_text
            # Answer line
            elif upper.startswith("ANS:"):
                ans_raw = line[4:].strip()
            elif upper.startswith("ANSWER:"):
                ans_raw = line[7:].strip()
            # Explanation line
            elif upper.startswith("EXP:"):
                exp = line[4:].strip()
            elif upper.startswith("EXPLANATION:"):
                exp = line[12:].strip()

        # Validate: question + 4 options + answer sab hone chahiye
        if not qtext or not all(opts) or not ans_raw:
            continue

        m = re.search(r"[ABCD]", ans_raw.upper())
        if not m:
            continue
        ans_letter = m.group(0).upper()
        if ans_letter not in ANSWER_MAP:
            continue

        # Telegram poll limits: Q<=300 chars, option<=100 chars
        if len(qtext) > 300:
            qtext = qtext[:297] + "..."
        opts = [o[:100] if len(o) > 100 else o for o in opts]
        if len(exp) > 200:
            exp = exp[:197] + "..."

        qs.append({
            "question": qtext,
            "options": opts,
            "correct": ANSWER_MAP[ans_letter],
            "explanation": exp,
        })

    return qs


def pdf_to_text(pdf_path):
    """PDF se text nikalo - pdfplumber prefer, fallback pypdf. Saaf karke do."""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        if text.strip():
            return clean_text(text)
    except Exception as e:
        logger.warning(f"pdfplumber fail: {e}")
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    except Exception as e:
        logger.warning(f"pypdf fail: {e}")
    return clean_text(text)

