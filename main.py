"""Entry point - python bot.py se bot start hota hai."""
import logging

from telegram import Update
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
import broadcast as bcm
import live as lvm
from telegram.ext import filters as _tg_filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


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
    # broadcast: channel/group link + admin jo bolega bot bhejega
    # NOTE: channel me /myid ya /linkhere post karo to CommandHandler usko
    # pakad leta hai (Type.CHANNEL_POST filter nahi hota) - isliye ye dono
    # command channel-post se bhi kaam karenge (broadcast.py me handled).
    app.add_handler(CommandHandler("myid", bcm.cmd_myid, filters=_tg_filters.ALL))
    app.add_handler(CommandHandler("linkhere", bcm.cmd_linkhere, filters=_tg_filters.ALL))
    app.add_handler(CommandHandler("unlinkhere", bcm.cmd_unlinkhere))
    app.add_handler(CommandHandler("targets", bcm.cmd_targets))
    app.add_handler(CommandHandler("addtarget", bcm.cmd_addtarget))
    app.add_handler(CommandHandler("deltarget", bcm.cmd_deltarget))
    app.add_handler(CommandHandler("broadcast", bcm.cmd_broadcast))
    app.add_handler(CommandHandler("send", bcm.cmd_send))
    app.add_handler(CommandHandler("autofwd", bcm.cmd_autofwd))
    # LIVE: admin ka test 30-30 sec gap se channel/group me
    app.add_handler(CommandHandler("live", lvm.cmd_live))
    app.add_handler(CommandHandler("livestop", lvm.cmd_livestop))
    app.add_handler(CommandHandler("livestatus", lvm.cmd_livestatus))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    # channel ki post aaye to linked groups me auto-forward
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, bcm.on_channel_post))
    # bot group me add ho to auto-link
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bcm.on_bot_added))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    # /send mode me photo/video/document bhi broadcast ho
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.COMMAND, handle_text_buttons))
    app.add_error_handler(on_error)
    # app.post_init = setup_menu_button  # ☰ menu button beside chat box hata diya gaya
    print("Bot starting (panels + menu button)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
