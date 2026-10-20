"""JSON storage - categories, subjects, tests, PDFs, history.

Thread-safe + atomic save (temp file + os.replace) + auto-backup.
"""
import json
import logging
import os
import tempfile
import threading

from config import BACKUP_FILE, DATA_FILE

logger = logging.getLogger(__name__)

db = {}
_lock = threading.RLock()


def default_db():
    return {
        "categories": {},
        "history": {},
        "users": {},
        "seq": {"cat": 0, "sub": 0, "test": 0},
        "broadcast": {"targets": {}, "autofwd": True, "source_channel": 0},
        "live": {"active": False, "cid": "", "sid": "", "tid": "", "gap": 30, "msg_ids": []},
    }


def _clean_str(s):
    if not isinstance(s, str):
        return s
    return s.replace("\x00", "").replace("\u0000", "").strip()


def _sanitize_loaded(d):
    """Purane data.json me ghuse NUL saaf karo + live/private flag default."""
    try:
        for c in (d.get("categories") or {}).values():
            if isinstance(c, dict) and "name" in c:
                c["name"] = _clean_str(c["name"])
            if isinstance(c, dict):
                c.setdefault("hidden", False)
            for s in (c.get("subjects") or {}).values():
                if isinstance(s, dict) and "name" in s:
                    s["name"] = _clean_str(s["name"])
                for t in (s.get("tests") or {}).values():
                    if not isinstance(t, dict):
                        continue
                    t["title"] = _clean_str(t.get("title", ""))
                    for q in t.get("questions", []) or []:
                        if not isinstance(q, dict):
                            continue
                        q["question"] = _clean_str(q.get("question", ""))
                        q["explanation"] = _clean_str(q.get("explanation", ""))
                        opts = q.get("options", [])
                        if isinstance(opts, list):
                            q["options"] = [_clean_str(o) for o in opts]
    except Exception as e:
        logger.warning(f"sanitize fail: {e}")
    return d


def load_data():
    global db
    with _lock:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if "categories" not in d:
                    d = default_db()
                d.setdefault("categories", {})
                d.setdefault("history", {})
                d.setdefault("users", {})
                d.setdefault("seq", {"cat": 0, "sub": 0, "test": 0})
                d.setdefault("broadcast", {"targets": {}, "autofwd": True, "source_channel": 0})
                d.setdefault("live", {"active": False, "cid": "", "sid": "", "tid": "", "gap": 30, "msg_ids": []})
                db = _sanitize_loaded(d)
                return db
            except Exception as e:
                logger.warning(f"data.json corrupt: {e}")
                try:
                    if DATA_FILE.exists():
                        with open(DATA_FILE, "rb") as src:
                            raw = src.read()
                        with open(str(BACKUP_FILE) + ".corrupt", "wb") as dst:
                            dst.write(raw)
                except Exception:
                    pass
        db = default_db()
        return db


def save_data():
    with _lock:
        try:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                if DATA_FILE.exists():
                    with open(DATA_FILE, "rb") as src:
                        raw = src.read()
                    with open(BACKUP_FILE, "wb") as dst:
                        dst.write(raw)
            except Exception:
                pass
            fd, tmp = tempfile.mkstemp(dir=str(DATA_FILE.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                os.replace(tmp, DATA_FILE)
            finally:
                try:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"save failed: {e}")


def new_id(prefix, kind):
    with _lock:
        db["seq"][kind] = db["seq"].get(kind, 0) + 1
        return f"{prefix}{db['seq'][kind]}"


def get_cat(cid):
    return db["categories"].get(cid)


def get_sub(cid, sid):
    c = get_cat(cid)
    if not c:
        return None
    return c.get("subjects", {}).get(sid)


def get_test(cid, sid, tid):
    s = get_sub(cid, sid)
    if not s:
        return None
    return s.get("tests", {}).get(tid)


def add_history(uid, entry):
    with _lock:
        db["history"].setdefault(str(uid), []).append(entry)
        if entry.get("name"):
            db.setdefault("users", {})[str(uid)] = entry["name"]
        save_data()


def get_history(uid):
    return db["history"].get(str(uid), [])


def get_leaderboard(limit=10):
    rows = []
    for uid, attempts in db.get("history", {}).items():
        if not attempts:
            continue
        name = db.get("users", {}).get(str(uid), f"User {uid}")
        best = max(a["score"] for a in attempts)
        best_total = max(a["total"] for a in attempts if a["score"] == best)
        rows.append({
            "uid": uid, "name": name, "best": best,
            "total": best_total, "attempts": len(attempts),
        })
    rows.sort(key=lambda r: (r["best"] / max(r["total"], 1), r["best"]), reverse=True)
    return rows[:limit]


def seed_demo():
    if db["categories"]:
        return
    with _lock:
        if db["categories"]:
            return
        # Simple system: ek hi category "General", uske andar Test 1, Test 2...
        cid = f"c{db['seq'].get('cat', 0) + 1}"
        db["seq"]["cat"] = db["seq"].get("cat", 0) + 1
        db["categories"][cid] = {"name": "General", "subjects": {}}
        sid = f"s{db['seq'].get('sub', 0) + 1}"
        db["seq"]["sub"] = db["seq"].get("sub", 0) + 1
        db["categories"][cid]["subjects"][sid] = {"name": "General", "pdfs": [], "tests": {}}
        tid = f"t{db['seq'].get('test', 0) + 1}"
        db["seq"]["test"] = db["seq"].get("test", 0) + 1
        db["categories"][cid]["subjects"][sid]["tests"][tid] = {
            "title": "Test 1",
            "questions": [
                {"question": "Bharat ki rajdhani?", "options": ["Mumbai", "Delhi", "Kolkata", "Chennai"], "correct": 1, "explanation": "Delhi rajdhani hai."},
                {"question": "2 + 2 = ?", "options": ["3", "4", "5", "6"], "correct": 1, "explanation": "2+2=4."},
                {"question": "RRB ka full form?", "options": ["Railway Recruitment Board", "Road Board", "Rural Bank", "None"], "correct": 0, "explanation": "Railway Recruitment Board."},
            ],
        }
        save_data()


def ensure_general():
    """Hamesha ek General/General jaga ho jisme Test 1,2,3... bante jayein."""
    with _lock:
        for cid, c in db.get("categories", {}).items():
            if (c.get("name") or "").strip().lower() == "general":
                for sid, s in (c.get("subjects") or {}).items():
                    if (s.get("name") or "").strip().lower() == "general":
                        return cid, sid
                sid = new_id("s", "sub")
                c.setdefault("subjects", {})[sid] = {"name": "General", "pdfs": [], "tests": {}}
                save_data()
                return cid, sid
        cid = new_id("c", "cat")
        db.setdefault("categories", {})[cid] = {"name": "General", "subjects": {}}
        sid = new_id("s", "sub")
        db["categories"][cid]["subjects"][sid] = {"name": "General", "pdfs": [], "tests": {}}
        save_data()
        return cid, sid


def next_test_number_in(cid, sid):
    """Us sub-category me agla Test number (har sub me Test 1, 2... alag)."""
    import re
    s = get_sub(cid, sid)
    tests = (s.get("tests", {}) or {}) if s else {}
    nums = []
    for t in tests.values():
        m = re.search(r"(\d+)", t.get("title", "") or "")
        if m:
            try:
                nums.append(int(m.group(1)))
            except ValueError:
                pass
    return (max(nums) + 1) if nums else (len(tests) + 1)


def next_test_number():
    """Purana General wala (backward compat)."""
    """General me agla Test number (Test 1, Test 2...)."""
    cid, sid = ensure_general()
    tests = db["categories"][cid]["subjects"][sid].get("tests", {})
    import re
    nums = []
    for t in tests.values():
        m = re.search(r"(\d+)", t.get("title", "") or "")
        if m:
            try:
                nums.append(int(m.group(1)))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else (len(tests) + 1)
    return cid, sid, n
