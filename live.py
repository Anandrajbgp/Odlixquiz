"""LIVE test - admin ke command se test channel/group me test ke time se."""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as dbm
import broadcast as bcm
from config import ADMIN_ID
logger = logging.getLogger(__name__)
DEFAULT_GAP = 30
IST = timezone(timedelta(hours=5, minutes=30))

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
        from keyboards import get_test_qtime
        qt = get_test_qtime(t=t)
        return f"LIVE chal raha: <b>{title}</b> ({n} Q bheje, ⏱ {qt}s/Q). /livestop se roko."
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
    from keyboards import get_test_qtime, fmt_qtime
    for cid, c in dbm.db.get("categories", {}).items():
        tag = " [LIVE]" if c.get("hidden") else ""
        for sid, s in (c.get("subjects") or {}).items():
            for tid, t in (s.get("tests") or {}).items():
                idx += 1
                nq = len(t.get("questions", []))
                qt = fmt_qtime(get_test_qtime(t=t))
                lines.append(f"{idx}. {c.get('name')}/{s.get('name')} - <b>{t.get('title')}</b> ({nq} Q, ⏱ {qt}){tag}")
    if idx == 0:
        return "Koi test nahi. Pehle category + PDF se test banao."
    lines.append("Bhejo: <code>/live 1</code> ya <code>/live Test 1</code> (test ka time lagega)")
    return "\n".join(lines)

async def _send_q_to_targets(context, q, qi, total, title, gap):
    from quiz import _safe_send_poll, live_active_poll_info
    tg = bcm.get_targets()
    sent = 0
    lv = _lv()
    qtext = f"Q{qi + 1}/{total}: {q['question']}"
    for cid in list(tg.keys()):
        try:
            kind = (tg.get(str(cid)) or {}).get("kind", "")
            is_channel = kind == "channel"
            msg = await _safe_send_poll(
                context.bot, bcm._parse_chat_id(cid),
                qtext,
                q["options"], q.get("correct", q.get("answer", 0)), q.get("explanation", ""),
                open_period=gap, anonymous=False)
            sent += 1
            try:
                lv.setdefault("msg_ids", []).append(msg.message_id)
                live_active_poll_info[msg.poll.id] = {
                    "correct": q.get("correct", q.get("answer", 0)),
                    "title": title
                }
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"live Q to {cid} fail: {e}")
    return sent

async def run_live(context, cid, sid, tid, gap: int | None, admin_chat_id: int):
    from quiz import live_user_scores
    live_user_scores.clear()
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
    lv.update({"active": True, "cid": cid, "sid": sid, "tid": tid, "gap": gap or 0, "msg_ids": []})
    dbm.save_data()
    # gap = test ka qtime (banate samay chuna). None/0 aaye to test ka time lo.
    from keyboards import get_test_qtime
    if not gap:
        gap = get_test_qtime(cid, sid, tid)
    gap = max(5, min(int(gap), 600))
    lv["gap"] = gap
    dbm.save_data()
    qs = t["questions"]
    total = len(qs)
    title = t.get("title", "")
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    head = (f"🔴 LIVE TEST shuru! <b>{c.get('name','')}/{s.get('name','') if s else ''} - {title}</b>\n"
        f"{total} Q, har {gap} sec me ek. Sab taiyaar!\n\n"
        f"⏹ Rokne ke liye admin ko <code>/livestop</code> bhejna hai.")
    try:
        from telegram import InlineKeyboardButton as _B, InlineKeyboardMarkup as _M
        # admin ko private me stop button bhejo
        try:
            stop_kb = _M([[ _B("⏹ LIVE Roko", callback_data="adm:livestop") ]])
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"🔴 LIVE chal raha: <b>{title}</b> ({total} Q, {gap}s/Q).\nNeeche button se roko:",
                parse_mode="HTML", reply_markup=stop_kb)
        except Exception as e:
            logger.warning(f"live stop btn fail: {e}")
        await bcm.broadcast_text(context, head)
    except Exception as e:
        logger.warning(f"live head fail: {e}")
    for qi, q in enumerate(qs):
        if not _lv().get("active"):
            break
        try:
            await _send_q_to_targets(context, q, qi, total, title, gap)
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
        from quiz import live_active_poll_info, live_user_scores
        if live_user_scores:
            sorted_scores = sorted(live_user_scores.values(), key=lambda x: x["score"], reverse=True)
            lb_lines = [
                f"🏆 <b>LIVE TEST LEADERBOARD: {title}</b> 🏆\n",
                f"Khatam! Total {total} Questions. Sabhi participants ke scores:\n"
            ]
            for rank, st in enumerate(sorted_scores[:15], 1):
                em = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"{rank}."))
                lb_lines.append(f"{em} <b>{st['name']}</b> — Score: <b>{st['score']}</b>/{total}")
            lb_text = "\n".join(lb_lines)
            try:
                await bcm.broadcast_text(context, lb_text)
            except Exception:
                pass
            live_user_scores.clear()
        live_active_poll_info.clear()

        next_info = get_next_scheduled_test_text()
        finish_text = f"🏁 <b>LIVE TEST KHATM!</b>\n<b>{title}</b> - {total} Questions poore ho gaye.{next_info}"
        try:
            await bcm.broadcast_text(context, finish_text)
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text=f"LIVE khatm: {title} ({total} Q).")
        except Exception:
            pass

def start_live_task(context, cid, sid, tid, gap, admin_chat_id):
    context.application.create_task(run_live(context, cid, sid, tid, gap, admin_chat_id))

def parse_schedule_time(s: str) -> datetime | None:
    """Parse time in 12-hour or 24-hour format.
    Accepts: 6:30 PM, 06:30 PM, 21:30, 2026-11-27 6:30 PM, 2026-11-27 18:30
    """
    s = s.strip()
    # List of possible formats (12-hour + 24-hour)
    formats = [
        "%Y-%m-%d %I:%M %p",   # 2026-11-27 6:30 PM
        "%Y-%m-%d %I:%M%p",    # 2026-11-27 6:30PM
        "%d-%m-%Y %I:%M %p",   # 27-11-2026 6:30 PM
        "%d-%m-%Y %I:%M%p",    # 27-11-2026 6:30PM
        "%Y-%m-%d %H:%M",      # 2026-11-27 18:30
        "%d-%m-%Y %H:%M",      # 27-11-2026 18:30
        "%I:%M %p",            # 6:30 PM
        "%I:%M%p",             # 6:30PM
        "%H:%M",               # 18:30
    ]
    from datetime import time as dtime, timedelta

    # IST (Bhagalpur) timezone
    IST = timezone(timedelta(hours=5, minutes=30))

    for fmt in formats:
        try:
            parsed = datetime.strptime(s, fmt)
            # If only time was given (no date), combine with today's date in IST
            if parsed.date() == datetime(1900, 1, 1).date():
                now = datetime.now(IST)
                dt = datetime.combine(now.date(), parsed.time()).replace(tzinfo=IST)
                if dt <= now:
                    dt += timedelta(days=1)
                return dt
            return parsed.replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def get_next_scheduled_test_text() -> str:
    schedules = dbm.db.get("schedules", [])
    now_dt = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    future = []
    for sch in schedules:
        try:
            dt = datetime.fromisoformat(sch["run_time"])
            if dt > now_dt:
                future.append((dt, sch))
        except Exception:
            pass
    if not future:
        return ""
    future.sort(key=lambda x: x[0])
    next_dt, next_sch = future[0]
    time_str = next_dt.strftime("%d-%m-%Y %I:%M %p")
    return (
        f"\n\n📌 <b>AGLA UPCOMING TEST:</b>\n"
        f"⏰ <b>Time:</b> {time_str}\n"
        f"📚 <b>Topic:</b> {next_sch.get('title', '?')}\n"
        f"Sabhi members tayyaar rahein! 🚀"
    )


async def scheduled_job_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    sch = job.data if job else None
    if not sch:
        return
    logger.info(f"Triggering scheduled live test via JobQueue: {sch.get('title')}")
    start_live_task(context, sch["cid"], sch["sid"], sch["tid"], None, sch["admin_chat_id"])
    try:
        await context.bot.send_message(
            chat_id=sch["admin_chat_id"],
            text=f"⏰ <b>Scheduled Live Test Shuru Ho Gaya!</b>\nTest: <b>{sch.get('title')}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to send schedule start notification: {e}")

    # Remove from persistence
    schedules = dbm.db.get("schedules", [])
    dbm.db["schedules"] = [s for s in schedules if s.get("sch_id") != sch.get("sch_id")]
    dbm.save_data()


async def reminder_job_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    sch = job.data if job else None
    if not sch:
        return
    try:
        dt = datetime.fromisoformat(sch["run_time"])
        time_str = dt.strftime("%I:%M %p")
    except Exception:
        time_str = "10 mins"

    text = (
        f"⏰ <b>10-MINUTE REMINDER!</b> ⏰\n\n"
        f"Test bas 10 minute mein shuru hone wala hai!\n"
        f"📚 <b>Topic:</b> {sch.get('title')}\n"
        f"🕐 <b>Exact Start Time:</b> {time_str}\n\n"
        f"Sabhi members live test ke liye tayyaar ho jayein! 🚀"
    )
    try:
        await bcm.broadcast_text(context, text)
    except Exception as e:
        logger.warning(f"Reminder broadcast fail: {e}")


def schedule_test_job(job_queue, sch_entry):
    if not job_queue:
        return
    try:
        run_dt = datetime.fromisoformat(sch_entry["run_time"])
        sch_key = sch_entry.get("sch_id", sch_entry.get("tid"))
        job_id = f"sch_{sch_key}"
        job_queue.run_once(
            scheduled_job_callback,
            when=run_dt,
            data=sch_entry,
            name=job_id
        )
        logger.info(f"JobQueue: Scheduled '{sch_entry.get('title')}' for {run_dt}")

        # Schedule 10-minute reminder
        reminder_dt = run_dt - timedelta(minutes=10)
        now_dt = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        if reminder_dt > now_dt:
            rem_id = f"rem_{sch_key}"
            job_queue.run_once(
                reminder_job_callback,
                when=reminder_dt,
                data=sch_entry,
                name=rem_id
            )
            logger.info(f"JobQueue: Scheduled 10-min reminder for {reminder_dt}")
    except Exception as e:
        logger.error(f"Failed to schedule job in JobQueue: {e}")


def remove_test_job(job_queue, sch_id):
    if not job_queue:
        return
    job_id = f"sch_{sch_id}"
    rem_id = f"rem_{sch_id}"
    for j in job_queue.get_jobs_by_name(job_id):
        j.schedule_removal()
    for j in job_queue.get_jobs_by_name(rem_id):
        j.schedule_removal()


def start_scheduler(app_or_context):
    app = getattr(app_or_context, "application", app_or_context)
    jq = getattr(app, "job_queue", None) or getattr(app_or_context, "job_queue", None)
    if not jq:
        logger.warning("JobQueue not available on application.")
        return
    schedules = list(dbm.db.get("schedules", []))
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    for sch in schedules:
        if "sch_id" not in sch:
            sch["sch_id"] = f"{sch['tid']}_{int(datetime.now().timestamp())}"
        try:
            run_dt = datetime.fromisoformat(sch["run_time"])
            if run_dt > now:
                schedule_test_job(jq, sch)
        except Exception as e:
            logger.error(f"Error restoring job {sch}: {e}")


def _is_admin(uid) -> bool:
    try:
        return bool(ADMIN_ID) and uid is not None and int(uid) == int(ADMIN_ID)
    except Exception:
        return False


async def cmd_live(update, context):
    if not _is_admin(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("Admin only.")
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text(live_tests_list(), parse_mode="HTML")
        return
    query = " ".join(args)
    res = None
    if query.isdigit():
        idx = int(query)
        mp = live_index_map()
        res = mp.get(idx)
    else:
        res = find_test_by_name(query)
    if not res:
        await update.effective_message.reply_text(f"❌ Test '{query}' nahi mila.\n\n{live_tests_list()}", parse_mode="HTML")
        return
    cid, sid, tid = res
    start_live_task(context, cid, sid, tid, None, update.effective_chat.id)
    await update.effective_message.reply_text("🚀 LIVE test starting...")


async def cmd_livestop(update, context):
    if not _is_admin(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("Admin only.")
        return
    lv = _lv()
    lv["active"] = False
    dbm.save_data()
    await update.effective_message.reply_text("⏹ LIVE test roka gaya.")


async def cmd_schedule(update, context):
    if not _is_admin(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("Admin only.")
        return
    import admin_live_schedule
    await admin_live_schedule.schedule_menu(update, context)


async def cmd_schedules(update, context):
    if not _is_admin(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("Admin only.")
        return
    import admin_live_schedule
    await admin_live_schedule.schlist(update, context)


async def cmd_cancelschedule(update, context):
    if not _is_admin(update.effective_user.id if update.effective_user else None):
        await update.effective_message.reply_text("Admin only.")
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("Usage: <code>/cancelschedule 1</code>", parse_mode="HTML")
        return
    idx_str = str(int(args[0]) - 1)
    import admin_live_schedule
    await admin_live_schedule.schdel(update, context, idx_str)


