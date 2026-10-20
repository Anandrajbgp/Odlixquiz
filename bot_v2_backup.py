import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PollAnswerHandler, filters, ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

# --- QUIZ BANK (10 Qs) ---
QUESTIONS = [
    {"question": "Kaun sa Trend Reversal pattern hai?",
     "options": ["Bullish Engulfing", "Bearish Engulfing", "Doji", "Hammer"],
     "correct": 0,
     "explanation": "Bullish Engulfing strong bullish reversal hai."},
    {"question": "Bearish Engulfing kya indicate karta hai?",
     "options": ["Uptrend continue", "Bearish reversal", "Sideways", "Kuch nahi"],
     "correct": 1,
     "explanation": "Top par banta hai, bearish reversal signal."},
    {"question": "Doji candle ka matlab?",
     "options": ["Strong buying", "Strong selling", "Indecision", "Trend confirm"],
     "correct": 2,
     "explanation": "Open approx close = confusion."},
    {"question": "Hammer kahan banta hai?",
     "options": ["Top-bearish", "Bottom-bullish reversal", "Beech-continue", "Ignore"],
     "correct": 1,
     "explanation": "Downtrend bottom par bullish hint."},
    {"question": "Stop-loss ka fayda?",
     "options": ["Profit badhana", "Loss limit karna", "Tax bachana", "Brokerage kam"],
     "correct": 1,
     "explanation": "Loss ko fixed level par rokta hai."},
]
MORE_QS = [
    {"question": "Support level kya hai?",
     "options": ["Upar se girna", "Neeche support lena", "Zero volume", "Market band"],
     "correct": 1,
     "explanation": "Support par buying se girna rukta hai."},
    {"question": "Resistance level kya hai?",
     "options": ["Girna rukna", "Upar rukna/girna", "No trade", "Profit book"],
     "correct": 1,
     "explanation": "Resistance par selling se upar rukta hai."},
    {"question": "Risk-reward 1:2 matlab?",
     "options": ["1 risk par 2 reward", "2 risk par 1 reward", "1 lot-2 lot", "Kuch nahi"],
     "correct": 0,
     "explanation": "1 rupya risk, 2 reward target."},
    {"question": "Moving Average ka kaam?",
     "options": ["Trend smooth dikhana", "Price fix", "Volume badhana", "Tax"],
     "correct": 0,
     "explanation": "Noise smooth karke trend batata hai."},
    {"question": "Sabse important rule?",
     "options": ["Full capital lagao", "Risk manage + discipline", "Tips blind follow", "No stop-loss"],
     "correct": 1,
     "explanation": "Risk management hi long-term jitata hai."},
]
QUESTIONS.extend(MORE_QS)


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                d.setdefault("pdfs", [])
                d.setdefault("scores", {})
                return d
        except Exception as e:
            logger.warning(f"data.json corrupt: {e}")
    return {"pdfs": [], "scores": {}}


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save failed: {e}")


db = load_data()
stored_pdfs = db["pdfs"]
user_scores = db["scores"]
active_polls: dict = {}


def get_score(uid: int, name: str = ""):
    k = str(uid)
    if k not in user_scores:
        user_scores[k] = {"score": 0, "attempted": 0, "best": 0, "name": name}
    if name:
        user_scores[k]["name"] = name
    return user_scores[k]


def get_user_keyboard():
    kb = [
        [KeyboardButton("📊 Take Trading Test"), KeyboardButton("📚 View PDFs")],
        [KeyboardButton("🏆 My Score"), KeyboardButton("❌ Cancel Test")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def get_admin_keyboard():
    kb = [
        [KeyboardButton("📊 Take Trading Test"), KeyboardButton("📚 View PDFs")],
        [KeyboardButton("🏆 My Score"), KeyboardButton("❌ Cancel Test")],
        [KeyboardButton("⚙️ Admin: View Total Uploads"),
         KeyboardButton("📤 Admin: Instructions")],
        [KeyboardButton("📈 Admin: All Scores")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def menu_for(uid: int):
    return get_admin_keyboard() if uid == ADMIN_ID else get_user_keyboard()

async def start_or_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    get_score(uid, name)
    save_data()
    if uid == ADMIN_ID:
        await update.message.reply_text(
            f"Hello Admin {name}! Welcome to your control panel.",
            reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text(
            f"Hello {name}! Welcome to Trading Test Bot. Option chuno:",
            reply_markup=get_user_keyboard())


async def send_question(chat_id: int, uid: int, qi: int, context: ContextTypes.DEFAULT_TYPE):
    q = QUESTIONS[qi]
    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Q{qi + 1}/{len(QUESTIONS)}: {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q["explanation"],
        is_anonymous=False,
        open_period=60,
    )
    active_polls[msg.poll.id] = {"correct": q["correct"], "qi": qi, "uid": uid}


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = get_score(uid, update.effective_user.first_name)
    st["score"] = 0
    st["attempted"] = 0
    save_data()
    await update.message.reply_text(
        f"Test shuru! Total {len(QUESTIONS)} Qs, har Q 60 sec.",
        reply_markup=menu_for(uid))
    await send_question(update.effective_chat.id, uid, 0, context)


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.poll_answer
    pid = ans.poll_id
    u = ans.user
    if pid not in active_polls or u is None:
        return
    info = active_polls.pop(pid)
    if info["uid"] != u.id:
        return
    picked = ans.option_ids[0] if ans.option_ids else -1
    st = get_score(u.id, u.first_name)
    st["attempted"] += 1
    ok = (picked == info["correct"])
    if ok:
        st["score"] += 1
    save_data()
    nxt = info["qi"] + 1
    try:
        await context.bot.send_message(
            chat_id=u.id, text="Sahi!" if ok else "Galat!")
    except Exception:
        pass
    if nxt < len(QUESTIONS):
        try:
            await send_question(u.id, u.id, nxt, context)
        except Exception as e:
            logger.error(f"next Q failed: {e}")
    else:
        total = len(QUESTIONS)
        sc = st["score"]
        if sc > st.get("best", 0):
            st["best"] = sc
        save_data()
        em = "🏆" if sc >= 8 else "👍" if sc >= 5 else "📚"
        try:
            await context.bot.send_message(
                chat_id=u.id,
                text=f"{em} Test khatam!\nScore: {sc}/{total}\nBest: {st['best']}/{total}")
        except Exception as e:
            logger.error(f"final score failed: {e}")

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    name = update.effective_user.first_name
    if text == "📊 Take Trading Test":
        await start_quiz(update, context)
    elif text == "📚 View PDFs":
        if not stored_pdfs:
            await update.message.reply_text("Abhi tak koi PDF upload nahi hui.")
        else:
            await update.message.reply_text("Ye rahe PDFs:")
            for p in stored_pdfs:
                try:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=p["file_id"],
                        caption=p.get("file_name", ""))
                except Exception as e:
                    logger.error(f"pdf send fail: {e}")
            await update.message.reply_text(f"Total PDFs: {len(stored_pdfs)}")
    elif text == "🏆 My Score":
        st = get_score(uid, name)
        await update.message.reply_text(
            f"Score: {st['score']}/{len(QUESTIONS)}\nAttempted: {st['attempted']}\nBest: {st.get('best', 0)}/{len(QUESTIONS)}",
            reply_markup=menu_for(uid))
    elif text == "❌ Cancel Test":
        for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
            active_polls.pop(pid, None)
        await update.message.reply_text("Test cancel.", reply_markup=menu_for(uid))
    elif text == "⚙️ Admin: View Total Uploads" and uid == ADMIN_ID:
        names = "\n".join([f"- {p.get('file_name', '?')}" for p in stored_pdfs]) or "(empty)"
        await update.message.reply_text(f"Total PDFs: {len(stored_pdfs)}\n{names}")
    elif text == "📤 Admin: Instructions" and uid == ADMIN_ID:
        await update.message.reply_text("Admin chat me .pdf bhejo, bot save kar lega (data.json).")
    elif text == "📈 Admin: All Scores" and uid == ADMIN_ID:
        if not user_scores:
            await update.message.reply_text("Kisi ne test nahi diya.")
        else:
            rows = sorted(user_scores.items(), key=lambda x: x[1].get("best", 0), reverse=True)[:20]
            lines = [f"{s.get('name', k)}: Best {s.get('best', 0)}/{len(QUESTIONS)}" for k, s in rows]
            await update.message.reply_text("Top Scores:\n" + "\n".join(lines))
    else:
        await start_or_menu(update, context)


async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        fid = update.message.document.file_id
        fname = update.message.document.file_name or "unnamed.pdf"
        stored_pdfs.append({"file_id": fid, "file_name": fname})
        save_data()
        await update.message.reply_text(f"Success! '{fname}' save. Total: {len(stored_pdfs)}")
    else:
        await update.message.reply_text("⛔ Permission nahi hai.")


def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing! .env me daalo.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_or_menu))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    print("Bot starting with upgraded features...")
    app.run_polling()


if __name__ == "__main__":
    main()

