"""LIVE test - admin ke command se test channel/group me 30-30 sec gap se."""
import asyncio
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
import database as dbm
import broadcast as bcm
from config import ADMIN_ID
logger = logging.getLogger(__name__)
DEFAULT_GAP = 30

def _lv():
    return dbm.db.setdefault(
        "live", {"active": False, "cid": "", "sid": "", "tid": "", "gap": 30, "msg_ids": []})

def is_live_active() -> bool:
    return bool(_lv().get("active"))

def live_status_text() -> str:
    lv = _lv()
    if lv.get("active"):
        t = dbm.get_test(lv.get("cid", ""), lv.get("sid", ""), lv.get("tid", ""))
        title = t.get("title", "?") if t else "?"
        n = len(lv.get("msg_ids", []))
        return f"LIVE chal raha: <b>{title}</b> ({n} Q bheje). /livestop se roko."
    return "Koi LIVE test nahi chal raha."

def live_index_map():
    mp = {}
    idx = 0
    for cid, c in dbm.db.get("categories", {}).items():
        for sid, s in (c.get("subjects") or {}).items():
            for tid in (s.get("tests") or {}).keys():
                idx += 1
                mp[idx] = (cid, sid, tid)
    return mp

def find_test_by_name(text: str):
    text = (text or "").strip().lower()
    if not text:
        return None
    for cid, c in dbm.db.get("categories", {}).items():
        for sid, s in (c.get("subjects") or {}).items():
            for tid, t in (s.get("tests") or {}).items():
                title = (t.get("title") or "").lower()
                if text == title or text in title:
                    return cid, sid, tid
    m = re.search(r"(\d+)", text)
    if m and len(text) <= 10:
        for cid, c in dbm.db.get("categories", {}).items():
            for sid, s in (c.get("subjects") or {}).items():
                for tid, t in (s.get("tests") or {}).items():
                    mt = re.search(r"(\d+)", (t.get("title") or "").lower())
                    if mt and mt.group(1) == m.group(1):
                        return cid, sid, tid
    return None

def live_tests_list() -> str:
    lines = ["<b>LIVE bhejne ke liye test chuno:</b>"]
    idx = 0
    for cid, c in dbm.db.get("categories", {}).items():
        tag = " [LIVE]" if c.get("hidden") else ""
        for sid, s in (c.get("subjects") or {}).items():
            for tid, t in (s.get("tests") or {}).items():
                idx += 1
                nq = len(t.get("questions", []))
                lines.append(f"{idx}. {c.get('name')}/{s.get('name')} - <b>{t.get('title')}</b> ({nq} Q){tag}")
    if idx == 0:
        return "Koi test nahi. Pehle category + PDF se test banao."
    lines.append("Bhejo: <code>/live 1</code> ya <code>/live Test 1</code>")
    return "\n".join(lines)

async def _send_q_to_targets(context, q, qi, total, title):
    from quiz import _safe_send_poll
    tg = bcm.get_targets()
    sent = 0
    lv = _lv()
    for cid in list(tg.keys()):
        try:
            kind = (tg.get(str(cid)) or {}).get("kind", "")
            is_channel = kind == "channel"
            msg = await _safe_send_poll(
                context.bot, int(cid),
                f"[LIVE {title}] Q{qi + 1}/{total}: {q['question']}",
                q["options"], q["correct"], q.get("explanation", ""),
                open_period=None, anonymous=is_channel)
            sent += 1
            try:
                lv.setdefault("msg_ids", []).append(msg.message_id)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"live Q to {cid} fail: {e}")
    return sent

async def run_live(context, cid, sid, tid, gap: int, admin_chat_id: int):
    lv = _lv()
    if lv.get("active"):
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text="Ek LIVE chal raha. /livestop se roko.")
        except Exception:
            pass
        return
    t = dbm.get_test(cid, sid, tid)
    if not t or not t.get("questions"):
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text="Test khali hai.")
        except Exception:
            pass
        return
    if not bcm.get_targets():
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text="Koi group linked nahi. /targets dekho.")
        except Exception:
            pass
        return
    lv.update({"active": True, "cid": cid, "sid": sid, "tid": tid, "gap": gap, "msg_ids": []})
    dbm.save_data()
    qs = t["questions"]
    total = len(qs)
    title = t.get("title", "")
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    head = (f"LIVE TEST shuru! <b>{c.get('name','')}/{s.get('name','') if s else ''} - {title}</b>\n"
        f"{total} Q, har {gap} sec me ek. Sab taiyaar!")
    try:
        await bcm.broadcast_text(context, head)
    except Exception as e:
        logger.warning(f"live head fail: {e}")
    for qi, q in enumerate(qs):
        if not _lv().get("active"):
            break
        try:
            await _send_q_to_targets(context, q, qi, total, title)
        except Exception as e:
            logger.error(f"live Q{qi} fail: {e}")
        if qi < total - 1:
            for _ in range(gap):
                await asyncio.sleep(1)
                if not _lv().get("active"):
                    break
    still_on = _lv().get("active")
    _lv()["active"] = False
    dbm.save_data()
    if still_on:
        try:
            await bcm.broadcast_text(context, f"LIVE TEST khatm! <b>{title}</b> - {total} Q ho gaye.")
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text=f"LIVE khatm: {title} ({total} Q).")
        except Exception:
            pass

def start_live_task(context, cid, sid, tid, gap, admin_chat_id):
    context.application.create_task(run_live(context, cid, sid, tid, gap, admin_chat_id))

async def cmd_live(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.effective_message.reply_text("Admin only.")
        return
    if is_live_active():
        await update.effective_message.reply_text("Ek LIVE chal raha. /livestop se roko.")
        return
    arg = " ".join(context.args).strip() if context.args else ""
    gap = DEFAULT_GAP
    if context.args:
        last = context.args[-1].lower()
        m = re.match(r"^(gap=)?(\d+)$", last)
        if m and len(context.args) > 1:
            gap = max(10, min(int(m.group(2)), 300))
            arg = " ".join(context.args[:-1]).strip()
    if not arg:
        await update.effective_message.reply_text(live_tests_list(), parse_mode="HTML")
        return
    found = None
    if arg.isdigit():
        found = live_index_map().get(int(arg))
    if not found:
        found = find_test_by_name(arg)
    if not found:
        await update.effective_message.reply_text(f"'{arg}' nahi mila.\n\n" + live_tests_list(), parse_mode="HTML")
        return
    cid, sid, tid = found
    t = dbm.get_test(cid, sid, tid)
    await update.effective_message.reply_text(
        f"LIVE shuru: <b>{t.get('title')}</b> ({len(t.get('questions', []))} Q, har {gap} sec).",
        parse_mode="HTML")
    start_live_task(context, cid, sid, tid, gap, update.effective_chat.id)

async def cmd_livestop(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    lv = _lv()
    if not lv.get("active"):
        await update.effective_message.reply_text("Koi LIVE nahi chal raha.")
        return
    lv["active"] = False
    dbm.save_data()
    await update.effective_message.reply_text("LIVE rok diya.")
    try:
        await bcm.broadcast_text(context, "LIVE TEST rok diya gaya.")
    except Exception:
        pass

async def cmd_livestatus(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.effective_message.reply_text(live_status_text(), parse_mode="HTML")
