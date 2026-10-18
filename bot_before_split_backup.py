import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    PollAnswerHandler, filters, ContextTypes,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

# ---------- DATA MODEL ----------
# db = {"categories": {cid: {"name": str, "subjects": {sid: {"name": str, "pdfs": [{file_id,file_name}], "tests": {tid: {"title": str, "questions": [{question,options,correct,explanation}]}}}}}}, "history": {uid: [{date,cat,sub,test,score,total}]}, "seq": {"cat": int, "sub": int, "test": int}}

def default_db():
    return {"categories": {}, "history": {}, "seq": {"cat": 0, "sub": 0, "test": 0}}

def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            # purana format migrate (pdfs/scores)
            if "categories" not in d:
                d = default_db()
            d.setdefault("categories", {})
            d.setdefault("history", {})
            d.setdefault("seq", {"cat": 0, "sub": 0, "test": 0})
            return d
        except Exception as e:
            logger.warning(f"data.json corrupt: {e}")
    db0 = default_db()
    return db0

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save failed: {e}")

db = load_data()

def new_id(prefix, kind):
    db["seq"][kind] = db["seq"].get(kind, 0) + 1
    return f"{prefix}{db['seq'][kind]}"

def get_cat(cid):
    return db["categories"].get(cid)

def get_sub(cid, sid):
    c = get_cat(cid)
    if not c:
        return None
    return c["subjects"].get(sid)

def get_test(cid, sid, tid):
    s = get_sub(cid, sid)
    if not s:
        return None
    return s["tests"].get(tid)

def seed_demo():
    if db["categories"]:
        return
    # Demo: RRB / SSC / 12th
    for cat_name, subs in [("RRB", ["GK", "Science"]), ("SSC", ["Maths", "Reasoning"]), ("12th", ["Physics", "Chemistry", "Biology"])]:
        cid = new_id("c", "cat")
        db["categories"][cid] = {"name": cat_name, "subjects": {}}
        for sn in subs:
            sid = new_id("s", "sub")
            db["categories"][cid]["subjects"][sid] = {"name": sn, "pdfs": [], "tests": {}}
    # ek demo test RRB/GK me
    cid = list(db["categories"].keys())[0]
    sid = list(db["categories"][cid]["subjects"].keys())[0]
    tid = new_id("t", "test")
    db["categories"][cid]["subjects"][sid]["tests"][tid] = {"title": "Demo Set 1 (5 Qs)", "questions": [
        {"question": "Bharat ki rajdhani?", "options": ["Mumbai", "Delhi", "Kolkata", "Chennai"], "correct": 1, "explanation": "Delhi rajdhani hai."},
        {"question": "2 + 2 = ?", "options": ["3", "4", "5", "6"], "correct": 1, "explanation": "2+2=4."},
        {"question": "RRB ka full form?", "options": ["Railway Recruitment Board", "Road Board", "Rural Bank", "None"], "correct": 0, "explanation": "Railway Recruitment Board."},
    ]}
    save_data()

seed_demo()

active_polls: dict = {}
def user_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📝 Test Do"), KeyboardButton("📚 PDFs")],
         [KeyboardButton("📜 History"), KeyboardButton("❌ Cancel")]],
        resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📝 Test Do"), KeyboardButton("📚 PDFs")],
         [KeyboardButton("📜 History"), KeyboardButton("❌ Cancel")],
         [KeyboardButton("➕ Add Category"), KeyboardButton("📁 Add Subject")],
         [KeyboardButton("📝 Add Test"), KeyboardButton("📄 PDF se Test")],
         [KeyboardButton("📤 Upload PDFs"), KeyboardButton("📊 Stats")]],
        resize_keyboard=True)

def menu_for(uid):
    return admin_menu() if uid == ADMIN_ID else user_menu()

def cat_inline(prefix):
    btns = []
    for cid, c in db["categories"].items():
        nsub = len(c["subjects"])
        ntest = sum(len(s["tests"]) for s in c["subjects"].values())
        npdf = sum(len(s["pdfs"]) for s in c["subjects"].values())
        btns.append([InlineKeyboardButton(
            f"📂 {c['name']} ({nsub} sub, {ntest} test, {npdf} pdf)",
            callback_data=f"{prefix}:{cid}")])
    if not btns:
        btns = [[InlineKeyboardButton("Empty", callback_data="noop")]]
    return InlineKeyboardMarkup(btns)

def sub_inline(prefix, cid):
    c = get_cat(cid)
    if not c:
        return None
    btns = []
    for sid, s in c["subjects"].items():
        btns.append([InlineKeyboardButton(
            f"📁 {s['name']} ({len(s['tests'])} test, {len(s['pdfs'])} pdf)",
            callback_data=f"{prefix}:{cid}:{sid}")])
    btns.append([InlineKeyboardButton("⬅ Back", callback_data=f"back:{prefix}")])
    return InlineKeyboardMarkup(btns)

def test_inline(cid, sid):
    s = get_sub(cid, sid)
    if not s:
        return None
    btns = []
    for tid, t in s["tests"].items():
        btns.append([InlineKeyboardButton(
            f"📝 {t['title']} ({len(t['questions'])} Qs)",
            callback_data=f"start:{cid}:{sid}:{tid}")])
    btns.append([InlineKeyboardButton("⬅ Back", callback_data=f"bsub:{cid}")])
    return InlineKeyboardMarkup(btns)

async def start_or_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    context.user_data.pop("astate", None)
    if uid == ADMIN_ID:
        await update.message.reply_text(f"Hello Admin {name}! Category→Subject system ready.", reply_markup=admin_menu())
    else:
        await update.message.reply_text(f"Hello {name}! Category chuno:", reply_markup=user_menu())
    if db["categories"]:
        await update.message.reply_text("📂 Category select karo:", reply_markup=cat_inline("browse"))

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    h = db["history"].get(uid, [])
    if not h:
        await update.message.reply_text("📜 Abhi koi test history nahi hai. 📝 Test Do dabao!")
        return
    lines = []
    for e in h[-10:][::-1]:
        lines.append(f"{e.get('date','')} | {e.get('cat','')}/{e.get('sub','')} | {e.get('test','')} → {e.get('score')}/{e.get('total')}")
    best = max(x["score"] for x in h)
    await update.message.reply_text(f"📜 Last {len(lines)} tests (Best: {best}):\n" + "\n".join(lines))

async def send_q(chat_id, uid, cid, sid, tid, qi, context):
    t = get_test(cid, sid, tid)
    q = t["questions"][qi]
    total = len(t["questions"])
    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"[{t['title']}] Q{qi+1}/{total}: {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q.get("explanation", ""),
        is_anonymous=False,
        open_period=120,
    )
    active_polls[msg.poll.id] = {"cid": cid, "sid": sid, "tid": tid, "qi": qi, "uid": uid}

async def begin_test(chat_id, uid, cid, sid, tid, context):
    t = get_test(cid, sid, tid)
    c = get_cat(cid); s = get_sub(cid, sid)
    if not t or not t["questions"]:
        await context.bot.send_message(chat_id=chat_id, text="❌ Is test me questions nahi hain.")
        return
    context.user_data.pop("astate", None)
    for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
        active_polls.pop(pid, None)
    await context.bot.send_message(chat_id=chat_id, text=f"🚀 {c['name']} → {s['name']} → {t['title']}\nTotal {len(t['questions'])} Qs. Good luck!")
    await send_q(chat_id, uid, cid, sid, tid, 0, context)

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.poll_answer
    u = ans.user
    if not u or ans.poll_id not in active_polls:
        return
    info = active_polls.pop(ans.poll_id)
    if info["uid"] != u.id:
        return
    t = get_test(info["cid"], info["sid"], info["tid"])
    if not t:
        return
    total = len(t["questions"])
    picked = ans.option_ids[0] if ans.option_ids else -1
    correct = (picked == t["questions"][info["qi"]]["correct"])
    live = context.bot_data.setdefault("live", {}).setdefault(u.id, {"score": 0, "done": 0})
    # score bot_data me carry hota hai (poll_answer me user_data nahi milta)
    live["done"] = live.get("done", 0) + 1
    if correct:
        live["score"] = live.get("score", 0) + 1
    nxt = info["qi"] + 1
    try:
        await context.bot.send_message(chat_id=u.id, text="✅ Sahi!" if correct else "❌ Galat!")
    except Exception:
        pass
    if nxt < total:
        info2 = dict(info); info2["qi"] = nxt
        try:
            q = t["questions"][nxt]
            msg = await context.bot.send_poll(
                chat_id=u.id,
                question=f"[{t['title']}] Q{nxt+1}/{total}: {q['question']}",
                options=q["options"], type="quiz",
                correct_option_id=q["correct"],
                explanation=q.get("explanation", ""),
                is_anonymous=False, open_period=120)
            active_polls[msg.poll.id] = info2
        except Exception as e:
            logger.error(f"next Q fail: {e}")
    else:
        live_all = context.bot_data.get("live", {}).pop(u.id, live)
        sc = live_all.get("score", 0)
        c = get_cat(info["cid"]); s = get_sub(info["cid"], info["sid"])
        entry = {"date": datetime.now().strftime("%d-%m %H:%M"), "cat": c["name"] if c else "",
                 "sub": s["name"] if s else "", "test": t["title"], "score": sc, "total": total}
        db["history"].setdefault(str(u.id), []).append(entry)
        save_data()
        em = "🏆" if sc == total else "👍" if sc * 2 >= total else "📚"
        try:
            await context.bot.send_message(chat_id=u.id, text=f"{em} Khatam!\n{t['title']}: {sc}/{total}\n📜 History me save ho gaya.")
        except Exception as e:
            logger.error(f"final fail: {e}")

Q_FMT = "Q: Sawal? | A | B | C | D | Ans: A/B/C/D | Exp: ... (har line 1 Q)"

def pdf_to_text(pdf_path):
    """PDF se text nikalo - pdfplumber prefer, fallback pypdf."""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        if text.strip():
            return text
    except Exception as e:
        logger.warning(f"pdfplumber fail: {e}")
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    except Exception as e:
        logger.warning(f"pypdf fail: {e}")
    return text

def parse_questions(text):
    qs = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or not line.startswith("Q:"):
            continue
        parts = [p.strip() for p in line[2:].split("|")]
        if len(parts) < 6:
            continue
        qtext = parts[0]
        opts = parts[1:5]
        ans_raw = parts[5].replace("Ans:", "").strip().upper()
        m = {"A": 0, "B": 1, "C": 2, "D": 3}
        if ans_raw not in m:
            continue
        exp = ""
        if len(parts) > 6 and parts[6].lower().startswith("exp:"):
            exp = parts[6][4:].strip()
        qs.append({"question": qtext, "options": opts, "correct": m[ans_raw], "explanation": exp})
    return qs

async def admin_text_step(update, context):
    txt = update.message.text.strip()
    st = context.user_data.get("astate")
    if not st:
        return False
    step = st.get("step")
    if step == "wait_cat_name":
        cid = new_id("c", "cat")
        db["categories"][cid] = {"name": txt[:60], "subjects": {}}
        save_data()
        context.user_data.pop("astate", None)
        await update.message.reply_text(f"✅ Category '{txt}' add!", reply_markup=admin_menu())
        await update.message.reply_text("📂 Categories:", reply_markup=cat_inline("asub"))
        return True
    if step == "wait_sub_name":
        c = get_cat(st["cid"])
        if not c:
            context.user_data.pop("astate", None)
            return True
        sid = new_id("s", "sub")
        c["subjects"][sid] = {"name": txt[:60], "pdfs": [], "tests": {}}
        save_data()
        context.user_data.pop("astate", None)
        await update.message.reply_text(f"✅ Subject '{txt}' → {c['name']}!", reply_markup=admin_menu())
        return True
    if step == "wait_test_title":
        st["title"] = txt[:80]
        st["step"] = "wait_test_body"
        await update.message.reply_text(f"Title: {txt}\nAb questions bhejo:\n{Q_FMT}\nEx:\nQ: 2+2? | 3 | 4 | 5 | 6 | Ans: B | Exp: 2+2=4")
        return True
    if step == "wait_test_body":
        qs = parse_questions(txt)
        if not qs:
            await update.message.reply_text("❌ Valid Q nahi mila. Format me bhejo.")
            return True
        s = get_sub(st["cid"], st["sid"])
        tid = new_id("t", "test")
        s["tests"][tid] = {"title": st["title"], "questions": qs}
        save_data()
        c = get_cat(st["cid"])
        context.user_data.pop("astate", None)
        await update.message.reply_text(f"✅ Test '{st['title']}' save! {len(qs)} Qs → {c['name']}/{s['name']}", reply_markup=admin_menu())
        return True
    return False

async def handle_text_buttons(update, context):
    text = update.message.text
    uid = update.effective_user.id
    if uid == ADMIN_ID and context.user_data.get("astate"):
        if await admin_text_step(update, context):
            return
    if text == "📝 Test Do":
        if not db["categories"]:
            await update.message.reply_text("Koi category nahi.")
            return
        await update.message.reply_text("📂 Category:", reply_markup=cat_inline("browse"))
    elif text == "📚 PDFs":
        await update.message.reply_text("📂 Category:", reply_markup=cat_inline("pdf"))
    elif text == "📜 History":
        await show_history(update, context)
    elif text == "❌ Cancel":
        context.user_data.pop("astate", None)
        for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
            active_polls.pop(pid, None)
        await update.message.reply_text("Cancel.", reply_markup=menu_for(uid))
    elif text == "➕ Add Category" and uid == ADMIN_ID:
        context.user_data["astate"] = {"step": "wait_cat_name"}
        await update.message.reply_text("Category naam bhejo (RRB/SSC/12th):")
    elif text == "📁 Add Subject" and uid == ADMIN_ID:
        context.user_data["astate"] = {"step": "pick_cat_for_sub"}
        await update.message.reply_text("Category chuno:", reply_markup=cat_inline("asub"))
    elif text == "📝 Add Test" and uid == ADMIN_ID:
        context.user_data["astate"] = {"step": "pick_cat_for_test"}
        await update.message.reply_text("Category chuno (text se test):", reply_markup=cat_inline("atest"))
    elif text == "📄 PDF se Test" and uid == ADMIN_ID:
        context.user_data["astate"] = {"step": "pick_cat_for_testpdf"}
        await update.message.reply_text("Kis category me PDF-test add karna hai? (Q-format wali PDF bhejoge)", reply_markup=cat_inline("atestpdf"))
    elif text == "📤 Upload PDFs" and uid == ADMIN_ID:
        context.user_data["astate"] = {"step": "pick_cat_for_pdf"}
        await update.message.reply_text("Category chuno (bulk PDFs bhej sakte ho):", reply_markup=cat_inline("apdf"))
    elif text == "📊 Stats" and uid == ADMIN_ID:
        nc = len(db["categories"])
        ns = sum(len(c["subjects"]) for c in db["categories"].values())
        nt = sum(len(s["tests"]) for c in db["categories"].values() for s in c["subjects"].values())
        nq = sum(len(t["questions"]) for c in db["categories"].values() for s in c["subjects"].values() for t in s["tests"].values())
        npdf = sum(len(s["pdfs"]) for c in db["categories"].values() for s in c["subjects"].values())
        nh = sum(len(v) for v in db["history"].values())
        await update.message.reply_text(f"Stats\nCat:{nc} Sub:{ns} Tests:{nt} Qs:{nq} PDFs:{npdf} Attempts:{nh}")
    else:
        await start_or_menu(update, context)

async def on_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data or ""
    st = context.user_data.get("astate", {})
    if data == "noop":
        return
    if data.startswith("browse:"):
        cid = data.split(":")[1]
        c = get_cat(cid)
        if c:
            await q.message.reply_text(f"📁 {c['name']} → Subject:", reply_markup=sub_inline("bsub", cid))
    elif data.startswith("bsub:"):
        cid = data.split(":")[1]
        c = get_cat(cid)
        if c:
            await q.message.reply_text(f"📝 {c['name']} → Test ke liye subject:", reply_markup=sub_inline("tsub", cid))
    elif data.startswith("tsub:"):
        _, cid, sid = data.split(":")
        s = get_sub(cid, sid)
        if s:
            if not s["tests"]:
                await q.message.reply_text("Is subject me koi test nahi.")
                return
            await q.message.reply_text(f"📝 {s['name']} → Test chuno:", reply_markup=test_inline(cid, sid))
    elif data.startswith("start:"):
        _, cid, sid, tid = data.split(":")
        await begin_test(q.message.chat_id, uid, cid, sid, tid, context)
    elif data.startswith("pdf:"):
        cid = data.split(":")[1]
        c = get_cat(cid)
        if c:
            await q.message.reply_text(f"📚 {c['name']} → Subject:", reply_markup=sub_inline("psub", cid))
    elif data.startswith("psub:"):
        _, cid, sid = data.split(":")
        s = get_sub(cid, sid)
        c = get_cat(cid)
        if s:
            if not s["pdfs"]:
                await q.message.reply_text(f"{c['name']}/{s['name']} me koi PDF nahi.")
                return
            await q.message.reply_text(f"📚 {c['name']}/{s['name']} PDFs:")
            for p in s["pdfs"]:
                try:
                    await context.bot.send_document(chat_id=q.message.chat_id, document=p["file_id"], caption=p.get("file_name", ""))
                except Exception as e:
                    logger.error(f"pdf fail: {e}")
    elif data.startswith("asub:"):
        cid = data.split(":")[1]
        st["step"] = "wait_sub_name"; st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text("Subject naam bhejo:")
    elif data.startswith("atest:"):
        cid = data.split(":")[1]
        st["step"] = "wait_sub_for_test"; st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text("Subject chuno:", reply_markup=sub_inline("tsub2", cid))
    elif data.startswith("tsub2:"):
        _, cid, sid = data.split(":")
        st["step"] = "wait_test_title"; st["cid"] = cid; st["sid"] = sid
        context.user_data["astate"] = st
        await q.message.reply_text("Test ka title bhejo (jaise Set-1 100 Qs):")
    elif data.startswith("atestpdf:"):
        cid = data.split(":")[1]
        st["step"] = "wait_sub_for_testpdf"; st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text("Subject chuno, phir Q-format wali PDF(s) bhejo:", reply_markup=sub_inline("tsubpdf", cid))
    elif data.startswith("tsubpdf:"):
        _, cid, sid = data.split(":")
        st["step"] = "uploading_test_pdf"; st["cid"] = cid; st["sid"] = sid; st["count"] = 0
        context.user_data["astate"] = st
        c = get_cat(cid); s = get_sub(cid, sid)
        await q.message.reply_text(
            f"✅ {c['name']}/{s['name']} select! Ab Q-format wali PDF bhejo.\nFormat:\nQ: Sawal? | A | B | C | D | Ans: B | Exp: ...\nTest ka naam PDF ke naam se banega.\nKhatam ho to ❌ Cancel.")
    elif data.startswith("apdf:"):
        cid = data.split(":")[1]
        st["step"] = "wait_sub_for_pdf"; st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text("Subject chuno, phir PDFs bhejo:", reply_markup=sub_inline("psub2", cid))
    elif data.startswith("psub2:"):
        _, cid, sid = data.split(":")
        st["step"] = "uploading_pdf"; st["cid"] = cid; st["sid"] = sid; st["count"] = 0
        context.user_data["astate"] = st
        c = get_cat(cid); s = get_sub(cid, sid)
        await q.message.reply_text(f"✅ {c['name']}/{s['name']} select! Ab bulk me PDFs bhejo (100 tak). Khatam ho to ❌ Cancel dabao.")
    elif data.startswith("back:"):
        await q.message.reply_text("📂 Category:", reply_markup=cat_inline("browse"))

async def handle_pdf(update, context):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Permission nahi.")
        return
    st = context.user_data.get("astate", {})
    step = st.get("step")
    # --- Flow A: study PDF (sirf padhne ke liye save) ---
    if step == "uploading_pdf":
        s = get_sub(st["cid"], st["sid"])
        if not s:
            await update.message.reply_text("❌ Subject nahi mila.")
            return
        fid = update.message.document.file_id
        fname = update.message.document.file_name or "unnamed.pdf"
        s["pdfs"].append({"file_id": fid, "file_name": fname})
        st["count"] = st.get("count", 0) + 1
        save_data()
        c = get_cat(st["cid"])
        await update.message.reply_text(f"✅ ({st['count']}) '{fname}' → {c['name']}/{s['name']}. Aur bhejo ya ❌ Cancel.")
        return
    # --- Flow B: test wali PDF (Q-format text se auto test) ---
    if step == "uploading_test_pdf":
        s = get_sub(st["cid"], st["sid"])
        c = get_cat(st["cid"])
        if not s:
            await update.message.reply_text("❌ Subject nahi mila.")
            return
        fname = update.message.document.file_name or "test.pdf"
        await update.message.reply_text(f"⏳ '{fname}' padh raha hoon, ruko...")
        try:
            tg_file = await context.bot.get_file(update.message.document.file_id)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            await tg_file.download_to_drive(tmp_path)
            raw = pdf_to_text(tmp_path)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"pdf download fail: {e}")
            await update.message.reply_text("❌ PDF download nahi ho payi. Dobara bhejo.")
            return
        qs = parse_questions(raw or "")
        if not qs:
            preview = (raw or "")[:500]
            await update.message.reply_text(
                f"❌ Is PDF me valid questions nahi mile.\nFormat aisa hona chahiye:\nQ: Sawal? | A | B | C | D | Ans: B | Exp: ...\n\nMila text (pehle 500 char):\n{preview}")
            return
        title = os.path.splitext(fname)[0][:80] or "PDF Test"
        tid = new_id("t", "test")
        s["tests"][tid] = {"title": title, "questions": qs, "source_pdf": fname}
        st["count"] = st.get("count", 0) + 1
        save_data()
        await update.message.reply_text(
            f"✅ Test ban gaya!\n📝 '{title}' → {c['name']}/{s['name']}\n❓ {len(qs)} questions\n\nUser ab 📝 Test Do → {c['name']} → {s['name']} → '{title}' se test de sakta hai (ek-ek Q poll me aayega).\nAur PDF bhejo ya ❌ Cancel.")
        return
    await update.message.reply_text("Pehle button dabao:\n📝 Add Test → 📄 PDF se (test banane ke liye)\n📤 Upload PDFs (sirf padhne wali PDF ke liye)")

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_or_menu))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    print("Bot starting (category system)...")
    app.run_polling()

if __name__ == "__main__":
    main()

