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
    """Multi-format question parser (handles Q:, Q1:, numbered questions, (A)/(B), Ans:, etc.)."""
    text = clean_text(text or "")
    qs = []
    lines = text.split("\n")

    # ---- Step 1: lines ko question-blocks mein todo ----
    blocks = []
    current_block = []
    q_start_re = re.compile(r"^(Q[\d\.\:\-\s]*|Question[\d\.\:\-\s]*|\d+[\.\)]\s+)", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_new = False
        if q_start_re.match(stripped):
            is_new = True

        if is_new and current_block:
            blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    # ---- Agar koi block nahi mila, single-line format try karein ----
    if not blocks:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue
            qtext = clean_text(parts[0])
            qtext = re.sub(r"^(Q[\d\.\:\-\s]*|Question[\d\.\:\-\s]*|\d+[\.\)]\s*)", "", qtext, flags=re.IGNORECASE).strip()
            opts = [_clean_opt(p) for p in parts[1:5]]
            if not qtext or any(not o for o in opts):
                continue
            ans_raw = clean_text(parts[5]).replace("Ans:", "").replace("ANS:", "").replace("Answer:", "").strip().upper()
            m = re.search(r"[ABCD1-4]", ans_raw)
            if not m:
                continue
            val = m.group(0).upper()
            ans_idx = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}.get(val, -1)
            if ans_idx < 0:
                continue
            exp = ""
            if len(parts) > 6 and "exp:" in parts[6].lower():
                exp = clean_text(parts[6].split(":", 1)[1] if ":" in parts[6] else parts[6])
            qs.append({
                "question": qtext[:300],
                "options": [o[:100] for o in opts],
                "correct": ans_idx,
                "explanation": exp[:200],
            })
        return qs

    # ---- Har block ko parse karein ----
    for block in blocks:
        qtext_lines = []
        opts = ["", "", "", ""]
        ans_raw = ""
        exp = ""

        for line in block:
            line_str = line.strip()
            if not line_str:
                continue
            upper = line_str.upper()

            # Option match: matches A), A., (A), [A], A:, a), 1), etc. (with optional space)
            opt_match = re.match(r"^[\(\[]?([A-Da-d1-4])[\)\.\:\-\]]\s*(.*)", line_str)
            if opt_match:
                opt_letter = opt_match.group(1).upper()
                opt_text = opt_match.group(2).strip()
                idx = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}.get(opt_letter, -1)
                if 0 <= idx < 4:
                    opts[idx] = opt_text
                continue

            # Answer match: Ans:, Answer:, Correct:, Ans - etc.
            if upper.startswith("ANS") or upper.startswith("CORRECT") or upper.startswith("ANSWER"):
                parts = re.split(r"[\:\-]\s*", line_str, 1)
                ans_raw = parts[1] if len(parts) > 1 else line_str
                continue

            # Explanation match: Exp:, Explanation:, Sol:, Solution: etc.
            if upper.startswith("EXP") or upper.startswith("EXPLANATION") or upper.startswith("SOL") or upper.startswith("SOLUTION"):
                parts = re.split(r"[\:\-]\s*", line_str, 1)
                exp = parts[1] if len(parts) > 1 else line_str
                continue

            # Question text line
            cleaned_line = line_str
            if not qtext_lines:
                cleaned_line = re.sub(r"^(Q[\d\.\:\-\s]*|Question[\d\.\:\-\s]*|\d+[\.\)]\s*)", "", line_str, flags=re.IGNORECASE).strip()

            if cleaned_line:
                qtext_lines.append(cleaned_line)

        qtext = " ".join(qtext_lines).strip()
        cleaned_opts = [_clean_opt(o) for o in opts]

        # Validation: question, 4 options, and answer must be present
        if not qtext or not all(cleaned_opts) or not ans_raw:
            continue

        m = re.search(r"[ABCD1-4]", ans_raw.upper())
        if not m:
            continue
        val = m.group(0).upper()
        ans_idx = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}.get(val, -1)
        if ans_idx < 0:
            continue

        if len(qtext) > 300:
            qtext = qtext[:297] + "..."
        cleaned_opts = [o[:100] if len(o) > 100 else o for o in cleaned_opts]
        if len(exp) > 200:
            exp = exp[:197] + "..."

        qs.append({
            "question": qtext,
            "options": cleaned_opts,
            "correct": ans_idx,
            "explanation": exp,
        })

    return qs
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

