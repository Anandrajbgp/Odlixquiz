"""Entry point - python bot.py se bot start hota hai."""
import logging
import os
import threading
from flask import Flask

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    PollAnswerHandler, filters,
)

import database as dbm
from config import BOT_TOKEN
from handlers_admin import handle_pdf
from handlers_user import (
    cmd_admin, cmd_cancel, cmd_home, cmd_leaderboard, cmd_test,
    handle_text_buttons, on_callback, show_history, start_or_menu,
)
from keyboards import setup_menu_button
from quiz import handle_poll_answer

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Keep-alive Flask server (Koyeb free tier ke liye) ----------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------------------------


async def on_error(update, context):
    """Global error handler - ek exception se bot crash nahi hoga."""
    logger.error(f"update {update} me error: {context.error}", exc_info=context.error)
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Kuch gadbad ho gayi. /start se dobara try karo.")
    except Exception:
        pass


def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing! .env me daalo.")
        return
    dbm.load_data()
    # seed_demo band: admin khud category + PDF se banayega
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_or_menu))
    app.add_handler(CommandHandler("home", cmd_home))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    app.add_error_handler(on_error)
    # app.post_init = setup_menu_button  # ☰ menu button beside chat box hata diya gaya

    # Flask server background mein start karo (Koyeb port pe listen karega)
    threading.Thread(target=run_flask, daemon=True).start()

    print("Bot starting (panels + keep-alive)...")
    app.run_polling()


if __name__ == "__main__":
    main()
