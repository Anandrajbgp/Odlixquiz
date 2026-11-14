"""JSON storage - Modularized structure.

Categories are in categories.json.
Subjects and Chapters (tests) are in quizzes/ folder:
quizzes/{cid}/{sid}/subject_info.json (contains subject metadata)
quizzes/{cid}/{sid}/{tid}.json (contains actual test/chapter data)
User data, history, and state are in users_data.json.
"""
import json
import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path

USERS_DATA_FILE = Path("users_data.json")
CATEGORIES_FILE = Path("categories.json")
QUIZZES_DIR = Path("quizzes")

logger = logging.getLogger(__name__)

db = {}
_lock = threading.RLock()


def default_db():
    return {
        "categories": {},
        "history": {},
        "users": {},
        "seq": {"cat": 0, "sub": 0, "test": 0},
        "broadcast": {
            "targets": {"@Odlixquizgroup": {"title": "Odlixquizgroup", "kind": "supergroup"}},
            "autofwd": True,
            "source_channel": 0
        },
        "live": {"active": False, "cid": "", "sid": "", "tid": "", "gap": 30, "msg_ids": []},
    }


def _clean_str(s):
    if not isinstance(s, str):
        return s
    return s.replace("\x00", "").replace("\u0000", "").strip()


def load_data():
    global db
    with _lock:
        db = default_db()

        # 1. Load User Data
        if USERS_DATA_FILE.exists():
            try:
                with open(USERS_DATA_FILE, "r", encoding="utf-8") as f:
                    user_d = json.load(f)
                db["history"] = user_d.get("history", {})
                db["users"] = user_d.get("users", {})
                db["seq"] = user_d.get("seq", {"cat": 0, "sub": 0, "test": 0})
                db["broadcast"] = user_d.get("broadcast", default_db()["broadcast"])
                db["live"] = user_d.get("live", default_db()["live"])
            except Exception as e:
                logger.error(f"Error loading {USERS_DATA_FILE}: {e}")

        # 2. Load Categories
        if CATEGORIES_FILE.exists():
            try:
                with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                    cats = json.load(f)
                    for c_id, c_data in cats.items():
                        c_data["name"] = _clean_str(c_data.get("name", ""))
                        c_data.setdefault("hidden", False)
                        c_data["subjects"] = {}
                        db["categories"][c_id] = c_data
            except Exception as e:
                logger.error(f"Error loading {CATEGORIES_FILE}: {e}")

        # 3. Load Subjects & Tests (Chapters)
        if QUIZZES_DIR.exists():
            for c_id in list(db["categories"].keys()):
                cat_dir = QUIZZES_DIR / c_id
                if not cat_dir.is_dir():
                    continue

                for sub_dir in cat_dir.iterdir():
                    if not sub_dir.is_dir():
                        continue
                    s_id = sub_dir.name

                    # Load subject info
                    info_file = sub_dir / "subject_info.json"
                    s_name, s_pdfs = "", []
                    if info_file.exists():
                        try:
                            with open(info_file, "r", encoding="utf-8") as f:
                                s_info = json.load(f)
                                s_name = _clean_str(s_info.get("name", ""))
                                s_pdfs = s_info.get("pdfs", [])
                        except Exception as e:
                            logger.error(f"Error loading {info_file}: {e}")

                    db["categories"][c_id]["subjects"][s_id] = {
                        "name": s_name,
                        "pdfs": s_pdfs,
                        "tests": {}
                    }

                    # Load tests/chapters
                    for test_file in sub_dir.glob("*.json"):
                        if test_file.name == "subject_info.json":
                            continue
                        t_id = test_file.stem
                        try:
                            with open(test_file, "r", encoding="utf-8") as f:
                                t_data = json.load(f)
                            t_data["title"] = _clean_str(t_data.get("title", ""))
                            for q in t_data.get("questions", []):
                                q["question"] = _clean_str(q.get("question", ""))
                                q["explanation"] = _clean_str(q.get("explanation", ""))
                                if isinstance(q.get("options"), list):
                                    q["options"] = [_clean_str(o) for o in q["options"]]
                            db["categories"][c_id]["subjects"][s_id]["tests"][t_id] = t_data
                        except Exception as e:
                            logger.error(f"Error loading test {test_file}: {e}")

        logger.info("Data loaded from chapter-level modular structure.")
        return db


def save_data():
    with _lock:
        try:
            # 1. User Data
            user_data = {
                "history": db.get("history", {}),
                "users": db.get("users", {}),
                "seq": db.get("seq", {}),
                "broadcast": db.get("broadcast", {}),
                "live": db.get("live", {})
            }
            _atomic_save(USERS_DATA_FILE, user_data)

            # 2. Categories
            cats_only = {}
            for c_id, c_data in db.get("categories", {}).items():
                cats_only[c_id] = {
                    "name": c_data.get("name", ""),
                    "hidden": c_data.get("hidden", False)
                }
            _atomic_save(CATEGORIES_FILE, cats_only)

            # 3. Subjects & Tests (Chapters)
            QUIZZES_DIR.mkdir(exist_ok=True)
            for c_id, c_data in db.get("categories", {}).items():
                cat_dir = QUIZZES_DIR / c_id
                cat_dir.mkdir(exist_ok=True)

                for s_id, s_data in c_data.get("subjects", {}).items():
                    sub_dir = cat_dir / s_id
                    sub_dir.mkdir(exist_ok=True)

                    info_data = {"name": s_data.get("name", ""), "pdfs": s_data.get("pdfs", [])}
                    _atomic_save(sub_dir / "subject_info.json", info_data)

                    for t_id, t_data in s_data.get("tests", {}).items():
                        _atomic_save(sub_dir / f"{t_id}.json", t_data)

        except Exception as e:
            logger.error(f"save failed: {e}")


def _atomic_save(file_path: Path, data: dict):
    fd, tmp = tempfile.mkstemp(dir=str(file_path.parent) if file_path.parent.exists() else ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(file_path))
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


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


def delete_cat(cid):
    with _lock:
        if cid in db["categories"]:
            del db["categories"][cid]
            cat_dir = QUIZZES_DIR / cid
            if cat_dir.exists():
                shutil.rmtree(cat_dir, ignore_errors=True)
            return True
        return False


def delete_sub(cid, sid):
    with _lock:
        c = get_cat(cid)
        if c and sid in c.get("subjects", {}):
            del c["subjects"][sid]
            sub_dir = QUIZZES_DIR / cid / sid
            if sub_dir.exists():
                shutil.rmtree(sub_dir, ignore_errors=True)
            return True
        return False


def delete_test(cid, sid, tid):
    with _lock:
        s = get_sub(cid, sid)
        if s and tid in s.get("tests", {}):
            del s["tests"][tid]
            test_file = QUIZZES_DIR / cid / sid / f"{tid}.json"
            if test_file.exists():
                test_file.unlink(missing_ok=True)
            return True
        return False


def get_history(uid):
    return db["history"].get(str(uid), [])


def add_history(uid, entry):
    with _lock:
        uid = str(uid)
        db["history"].setdefault(uid, [])
        db["history"][uid].append(entry)


def set_user_role(uid, role):
    with _lock:
        uid = str(uid)
        db["users"].setdefault(uid, {})
        db["users"][uid]["role"] = role


def get_user_role(uid):
    return db["users"].get(str(uid), {}).get("role", "user")


def log_live_msg(mid):
    with _lock:
        db["live"]["msg_ids"].append(mid)


def clear_live_msgs():
    with _lock:
        m = list(db["live"]["msg_ids"])
        db["live"]["msg_ids"] = []
        return m
