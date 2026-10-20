"""Broadcast - admin jo bolega bot group/channel me bhejega."""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
import database as dbm
from config import ADMIN_ID
logger = logging.getLogger(__name__)

def _bc():
    bc = dbm.db.setdefault("broadcast", {})
    bc.setdefault("targets", {})
    bc.setdefault("autofwd", True)
    bc.setdefault("source_channel", 0)
    return bc

def get_targets() -> dict:
    return _bc().get("targets", {})

def add_target(chat_id: int, title: str = "", kind: str = "") -> bool:
    bc = _bc()
    key = str(chat_id)
    is_new = key not in bc["targets"]
    bc["targets"][key] = {"title": title or key, "kind": kind or "?"}
    dbm.save_data()
    return is_new

def remove_target(chat_id) -> bool:
    bc = _bc()
    key = str(chat_id)
    if key in bc["targets"]:
        del bc["targets"][key]
        dbm.save_data()
        return True
    return False

def targets_text() -> str:
    tg = get_targets()
    if not tg:
        return ("📭 <b>Koi group/channel linked nahi.</b>\n\n"
            "1. Bot ko group/channel me add karke <b>Admin</b> banao\n"
            "2. Us group me <code>/linkhere</code> bhejo\n"
            "3. Ya yahan <code>/addtarget -100xxxx</code> bhejo\n"
            "ID ke liye us chat me <code>/myid</code> bhejo.")
    lines = [f"📡 <b>Linked Targets ({len(tg)}):</b>"]
    for cid, info in tg.items():
        lines.append(f"- <code>{cid}</code> - {info.get('title','?')} [{info.get('kind','?')}]")
    bc = _bc()
    lines.append(f"\nAuto-forward: <b>{'ON' if bc.get('autofwd', True) else 'OFF'}</b>")
    return "\n".join(lines)

async def _send_to_all(context, send_fn):
    tg = get_targets()
    if not tg:
        return 0, 0, ["Koi target linked nahi. Pehle /linkhere karo."]
    ok, fail, errs = 0, 0, []
    for cid in list(tg.keys()):
        try:
            await send_fn(int(cid))
            ok += 1
        except TelegramError as e:
            fail += 1
            errs.append(f"{cid}: {e}")
            msg = str(e).lower()
            if ("kicked" in msg or "not found" in msg or "blocked" in msg or "deactivated" in msg):
                try:
                    remove_target(cid)
                except Exception:
                    pass
        except Exception as e:
            fail += 1
            errs.append(f"{cid}: {e}")
    return ok, fail, errs

async def broadcast_text(context, text: str, parse_mode="HTML"):
    async def _one(cid):
        await context.bot.send_message(chat_id=cid, text=text, parse_mode=parse_mode)
    return await _send_to_all(context, _one)

async def broadcast_copy(update: Update, context):
    src = update.effective_message
    if not src:
        return 0, 0, ["message empty"]
    async def _one(cid):
        await context.bot.copy_message(chat_id=cid, from_chat_id=src.chat_id, message_id=src.message_id)
    return await _send_to_all(context, _one)

def _is_admin(uid: int) -> bool:
    return bool(ADMIN_ID) and uid == ADMIN_ID
async def cmd_myid(update, context):
    c = update.effective_chat
    await update.effective_message.reply_text(
        f"ID: <code>{c.id}</code>\nType: {c.type}\nTitle: {c.title or '-'}",
        parse_mode="HTML")

async def cmd_linkhere(update, context):
    if not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("Admin only.")
        return
    c = update.effective_chat
    if c.type == "private":
        await update.effective_message.reply_text(
            "Private chat link nahi hota. Group me /linkhere bhejo.",
            parse_mode="HTML")
        return
    add_target(c.id, c.title or c.username or "", c.type)
    await update.effective_message.reply_text(
        f"Linked! <b>{c.title or c.id}</b> (<code>{c.id}</code>). Ab /send se bhejo.",
        parse_mode="HTML")

async def cmd_unlinkhere(update, context):
    if not _is_admin(update.effective_user.id):
        return
    c = update.effective_chat
    if remove_target(c.id):
        await update.effective_message.reply_text(f"Unlinked {c.id}.")
    else:
        await update.effective_message.reply_text("Ye chat list me nahi tha.")

async def cmd_targets(update, context):
    if not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("Admin only.")
        return
    await update.effective_message.reply_text(targets_text(), parse_mode="HTML")

async def cmd_addtarget(update, context):
    if not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("Admin only.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Use: <code>/addtarget -1001234567890</code>", parse_mode="HTML")
        return
    raw = context.args[0].strip()
    chat_ref = raw
    try:
        chat_ref = int(raw)
    except ValueError:
        pass
    try:
        ch = await context.bot.get_chat(chat_ref)
        add_target(ch.id, ch.title or ch.username or raw, ch.type)
        await update.effective_message.reply_text(
            f"Linked! <b>{ch.title or ch.username or ch.id}</b> (<code>{ch.id}</code>)",
            parse_mode="HTML")
    except Exception as e:
        await update.effective_message.reply_text(
            f"Jod nahi paya. Bot us chat me Admin hai? Error: {e}")

async def cmd_deltarget(update, context):
    if not _is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.effective_message.reply_text("Use: <code>/deltarget -100xxxx</code>", parse_mode="HTML")
        return
    if remove_target(context.args[0].strip()):
        await update.effective_message.reply_text("Hata diya.")
    else:
        await update.effective_message.reply_text("Ye id list me nahi.")

async def cmd_broadcast(update, context):
    if not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("Admin only.")
        return
    text = " ".join(context.args) if context.args else ""
    if not text.strip() and update.effective_message.reply_to_message:
        r = update.effective_message.reply_to_message
        text = r.text or r.caption or ""
    if not text.strip():
        await update.effective_message.reply_text(
            "Use: <code>/broadcast Kal 9 baje test hai!</code>", parse_mode="HTML")
        return
    ok, fail, errs = await broadcast_text(context, text)
    rep = f"Broadcast: {ok} sent, {fail} fail."
    if errs:
        rep += "\n" + "\n".join(errs[:5])
    await update.effective_message.reply_text(rep)

async def cmd_send(update, context):
    if not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("Admin only.")
        return
    if not get_targets():
        await update.effective_message.reply_text(targets_text(), parse_mode="HTML")
        return
    context.user_data["astate"] = {"step": "wait_broadcast_msg"}
    await update.effective_message.reply_text(
        "Ab jo bhejoge wo sab linked groups me jayega. Bhejo ya /cancel karo.",
        parse_mode="HTML")

async def cmd_autofwd(update, context):
    if not _is_admin(update.effective_user.id):
        return
    arg = (context.args[0].lower() if context.args else "").strip()
    bc = _bc()
    if arg in ("on", "off"):
        bc["autofwd"] = (arg == "on")
        dbm.save_data()
        await update.effective_message.reply_text(f"Auto-forward: {arg.upper()}")
    else:
        st = "ON" if bc.get("autofwd", True) else "OFF"
        await update.effective_message.reply_text(f"Abhi: {st}. Use /autofwd on|off")

async def on_bot_added(update, context):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return
    try:
        me = await context.bot.get_me()
        members = update.effective_message.new_chat_members if update.effective_message else []
        if any(u.id == me.id for u in (members or [])):
            add_target(chat.id, chat.title or chat.username or "", chat.type)
    except Exception as e:
        logger.warning(f"on_bot_added fail: {e}")

async def on_channel_post(update, context):
    post = update.channel_post
    if not post:
        return
    bc = _bc()
    if not bc.get("autofwd", True):
        return
    tg = get_targets()
    if not tg:
        return
    src_id = post.chat_id
    for cid in list(tg.keys()):
        try:
            if int(cid) == src_id:
                continue
            await context.bot.copy_message(chat_id=int(cid), from_chat_id=src_id, message_id=post.message_id)
        except Exception as e:
            logger.warning(f"autofwd to {cid} fail: {e}")

