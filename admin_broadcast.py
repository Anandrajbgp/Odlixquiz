import database as dbm
import broadcast as bcm

async def send_start(update, context):
    q = update.callback_query
    if not bcm.get_targets():
        await q.message.reply_text(bcm.targets_text(), parse_mode="HTML")
    else:
        context.user_data["astate"] = {"step": "wait_broadcast_msg"}
        await q.message.reply_text(
            "📢 <b>Ab jo bhejoge wo sab linked groups/channels me jayega.</b>\n"
            "Text/photo/video/PDF kuch bhi bhejo ya /cancel karo.",
            parse_mode="HTML")

async def show_targets(update, context):
    q = update.callback_query
    await q.message.reply_text(bcm.targets_text(), parse_mode="HTML")

async def toggle_autofwd(update, context):
    q = update.callback_query
    bc = dbm.db.setdefault("broadcast", {})
    bc["autofwd"] = not bc.get("autofwd", True)
    dbm.save_data()
    st = "ON" if bc["autofwd"] else "OFF"
    await q.answer(f"Auto-forward is now {st}", show_alert=True)
