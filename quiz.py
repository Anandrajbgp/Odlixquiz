"""Quiz engine - poll bhejna, answer check, score + history.

- jawab aaye ya timeout ho, agla Q pakka jayega (atakta nahi)
- har attempt ka detail memory me taaki Review dikhe
"""
import asyncio
import logging
from datetime import datetime

from config import POLL_OPEN_SECONDS, TIMEOUT_GRACE
import database as dbm

logger = logging.getLogger(__name__)

# poll_id -> {cid, sid, tid, qi, uid}
active_polls: dict = {}
# uid -> current attempt detail list (review ke liye)
_attempt_details: dict = {}
# uid -> paused quiz state {cid, sid, tid, qi, score, done, total, title}
_paused_quizzes: dict = {}


def _live(context, uid):
    return context.bot_data.setdefault("live", {}).setdefault(
        uid, {"score": 0, "done": 0, "total": 0, "cid": "", "sid": "", "tid": "", "title": ""})


async def _safe_send_poll(bot, chat_id, question, options, correct, explanation, open_period=None, anonymous=False):
    question = (question or "")[:300]
    options = [(o or "")[:100] for o in (options or [])]
    explanation = (explanation or "")[:200]
    if len(options) < 2:
        raise ValueError("kam se kam 2 options chahiye")
    if open_period is None:
        open_period = POLL_OPEN_SECONDS
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options[:10],
        type="quiz",
        correct_option_id=max(0, min(correct, len(options) - 1)),
        explanation=explanation,
        is_anonymous=anonymous,
        open_period=open_period,
    )
    return msg


async def send_q(chat_id, uid, cid, sid, tid, qi, context, stop_msg_id=None):
    t = dbm.get_test(cid, sid, tid)
    q = t["questions"][qi]
    total = len(t["questions"])
    s = dbm.get_sub(cid, sid)
    sub_name = s["name"] if s else ""
    try:
        from keyboards import get_test_qtime
        timer = get_test_qtime(t=t)
    except Exception:
        timer = context.user_data.get("quiz_timer", POLL_OPEN_SECONDS)
    msg = await _safe_send_poll(
        context.bot, chat_id,
        f"[{sub_name}] Q{qi + 1}/{total}: {q['question']}",
        q["options"], q["correct"], q.get("explanation", ""),
        open_period=timer)
    active_polls[msg.poll.id] = {
        "cid": cid, "sid": sid, "tid": tid, "qi": qi, "uid": uid,
        "chat_id": chat_id, "start_time": datetime.now(),
    }
    context.application.create_task(_timeout_watch(msg.poll.id, uid, context))

    # Stop quiz button message (replaces previous one)
    from keyboards import stop_quiz_inline
    try:
        # Pehle naya stop button bhejo, phir purana hatayo
        stop_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="\u200b",
            reply_markup=stop_quiz_inline())
        if stop_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=stop_msg_id)
            except Exception:
                pass
        context.user_data["stop_msg_id"] = stop_msg.message_id
    except Exception as e:
        logger.error(f"stop button send fail: {e}")
    return msg


async def _timeout_watch(poll_id, uid, context):
    info0 = active_polls.get(poll_id)
    timer = None
    if info0:
        try:
            from keyboards import get_test_qtime as _gt
            timer = _gt(info0.get("cid"), info0.get("sid"), info0.get("tid"))
        except Exception:
            timer = None
    if not timer:
        timer = context.user_data.get("quiz_timer", POLL_OPEN_SECONDS)
    await asyncio.sleep(timer + TIMEOUT_GRACE)
    info = active_polls.pop(poll_id, None)
    if not info or info["uid"] != uid:
        return
    t = dbm.get_test(info["cid"], info["sid"], info["tid"])
    if not t:
        return
    live = _live(context, uid)
    live["done"] = live.get("done", 0) + 1
    elapsed = (datetime.now() - info["start_time"]).total_seconds()
    _attempt_details.setdefault(uid, []).append({
        "qi": info["qi"],
        "question": t["questions"][info["qi"]]["question"],
        "options": t["questions"][info["qi"]]["options"],
        "correct": t["questions"][info["qi"]]["correct"],
        "picked": -1,
        "timeout": True,
        "time_taken": round(elapsed, 1),
        "explanation": t["questions"][info["qi"]].get("explanation", ""),
    })
    try:
        await context.bot.send_message(chat_id=uid, text="⏰ Time khatm! Agla Q...")
    except Exception:
        pass
    await _advance(uid, info, context)


async def begin_test(chat_id, uid, cid, sid, tid, context):
    t = dbm.get_test(cid, sid, tid)
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    if not t or not t["questions"]:
        await context.bot.send_message(chat_id=chat_id, text="❌ This test has no questions.")
        return
    context.user_data.pop("astate", None)
    for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
        active_polls.pop(pid, None)
    context.bot_data.get("live", {}).pop(uid, None)
    _attempt_details.pop(uid, None)
    _paused_quizzes.pop(uid, None)
    context.user_data.pop("stop_msg_id", None)
    context.user_data.pop("feedback_msg_id", None)
    total = len(t["questions"])
    context.bot_data.setdefault("live", {})[uid] = {
        "score": 0, "done": 0, "total": total,
        "cid": cid, "sid": sid, "tid": tid, "title": t["title"],
    }
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🚀 <b>{c['name']} → {s['name']} → {t['title']}</b>\n"
             f"Total {total} Qs • Har Q ke liye {POLL_OPEN_SECONDS}s\nGood luck!",
        parse_mode="HTML")
    try:
        await send_q(chat_id, uid, cid, sid, tid, 0, context)
    except Exception as e:
        logger.error(f"first Q fail: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ Error sending first question. Try again.")


def cancel_live(uid, context):
    """Hard cancel - clear everything (used by /cancel command)."""
    for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
        active_polls.pop(pid, None)
    context.bot_data.get("live", {}).pop(uid, None)
    _attempt_details.pop(uid, None)
    _paused_quizzes.pop(uid, None)
    context.user_data.pop("stop_msg_id", None)
    context.user_data.pop("feedback_msg_id", None)


def pause_quiz(uid, context):
    """Save current progress and clear active polls so user can resume later."""
    live = context.bot_data.get("live", {}).get(uid)
    if not live:
        return None
    for pid in [k for k, v in active_polls.items() if v["uid"] == uid]:
        active_polls.pop(pid, None)
    _paused_quizzes[uid] = {
        "cid": live.get("cid", ""),
        "sid": live.get("sid", ""),
        "tid": live.get("tid", ""),
        "qi": live.get("done", 0),      # next question to show
        "score": live.get("score", 0),
        "done": live.get("done", 0),
        "total": live.get("total", 0),
        "title": live.get("title", ""),
    }
    context.user_data.pop("stop_msg_id", None)
    context.user_data.pop("feedback_msg_id", None)
    return _paused_quizzes[uid]


def resume_quiz(uid, context):
    """Restore paused quiz state and return it, or None if nothing paused."""
    return _paused_quizzes.get(uid)


def clear_paused(uid, context):
    """Clear paused quiz state (after resume or new test)."""
    _paused_quizzes.pop(uid, None)
    context.user_data.pop("stop_msg_id", None)


async def handle_poll_answer(update, context):
    ans = update.poll_answer
    u = ans.user
    if not u or ans.poll_id not in active_polls:
        return
    info = active_polls.pop(ans.poll_id)
    if info["uid"] != u.id:
        return
    # Purana feedback message hatayo taaki naya dikhe
    old_fb = context.user_data.pop("feedback_msg_id", None)
    if old_fb:
        try:
            await context.bot.delete_message(chat_id=u.id, message_id=old_fb)
        except Exception:
            pass
    t = dbm.get_test(info["cid"], info["sid"], info["tid"])
    if not t:
        return
    total = len(t["questions"])
    picked = ans.option_ids[0] if ans.option_ids else -1
    correct_idx = t["questions"][info["qi"]]["correct"]
    live = _live(context, u.id)
    live["done"] = live.get("done", 0) + 1
    if picked == correct_idx:
        live["score"] = live.get("score", 0) + 1
    elapsed = (datetime.now() - info["start_time"]).total_seconds()
    _attempt_details.setdefault(u.id, []).append({
        "qi": info["qi"],
        "question": t["questions"][info["qi"]]["question"],
        "options": t["questions"][info["qi"]]["options"],
        "correct": correct_idx,
        "picked": picked,
        "timeout": False,
        "time_taken": round(elapsed, 1),
        "explanation": t["questions"][info["qi"]].get("explanation", ""),
    })
    await _advance(u.id, info, context)


async def _advance(uid, info, context):
    """Agla Q bhejo ya test khatm karo. Answer + timeout dono yahi aate hain."""
    t = dbm.get_test(info["cid"], info["sid"], info["tid"])
    if not t:
        return
    total = len(t["questions"])
    nxt = info["qi"] + 1
    if nxt < total:
        info2 = dict(info)
        info2["qi"] = nxt
        try:
            stop_msg_id = context.user_data.get("stop_msg_id")
            msg = await send_q(info["chat_id"], uid, info["cid"], info["sid"], info["tid"], nxt, context,
                               stop_msg_id=stop_msg_id)
            active_polls[msg.poll.id] = info2
        except Exception as e:
            logger.error(f"next Q fail: {e}")
            live = _live(context, uid)
            live["done"] = live.get("done", 0) + 1
            await _advance(uid, info2, context)
    else:
        await finish_test(uid, info, context)


def result_card(title, score, total, details=None, total_time=None):
    pct = round(score * 100 / max(total, 1))
    if score == total:
        em, msg = "🏆", "Perfect!"
    elif pct >= 70:
        em, msg = "🎉", "Great job!"
    elif pct >= 40:
        em, msg = "👍", "Good effort — keep practicing."
    else:
        em, msg = "📚", "Don't give up — try again."
    bar_len = 10
    fill = round(pct / 10)
    bar = "🟩" * fill + "⬜" * (bar_len - fill)
    time_line = ""
    if total_time is not None:
        mins = int(total_time // 60)
        secs = int(total_time % 60)
        time_line = f"\n⏱ Total time: <b>{mins}m {secs}s</b>"
    return (
        f"{em} <b>Test Complete! {msg}</b>\n\n"
        f"📝 <b>{title}</b>\n"
        f"Score: <b>{score}/{total}</b> ({pct}%){time_line}\n{bar}\n\n"
        f"📜 Saved to history.")


async def finish_test(uid, info, context):
    t = dbm.get_test(info["cid"], info["sid"], info["tid"])
    if not t:
        return
    total = len(t["questions"])
    live_all = context.bot_data.get("live", {}).pop(uid, None) or {"score": 0}
    sc = live_all.get("score", 0)
    c = dbm.get_cat(info["cid"])
    s = dbm.get_sub(info["cid"], info["sid"])
    try:
        name = (await context.bot.get_chat(uid)).first_name or f"User {uid}"
    except Exception:
        name = f"User {uid}"
    entry = {
        "date": datetime.now().strftime("%d-%m %H:%M"),
        "cat": c["name"] if c else "",
        "sub": s["name"] if s else "",
        "test": t["title"],
        "score": sc,
        "total": total,
        "name": name,
        "cid": info["cid"], "sid": info["sid"], "tid": info["tid"],
    }
    dbm.add_history(uid, entry)
    details = list(_attempt_details.pop(uid, []))
    total_time = sum(d.get("time_taken", 0) for d in details)
    _paused_quizzes.pop(uid, None)
    context.user_data.pop("stop_msg_id", None)
    context.user_data.pop("feedback_msg_id", None)
    context.bot_data.setdefault("last_review", {})[uid] = {
        "title": t["title"], "score": sc, "total": total,
        "details": details,
    }
    from keyboards import result_keyboard
    try:
        await context.bot.send_message(
            chat_id=uid, text=result_card(t["title"], sc, total, details=details, total_time=total_time),
            parse_mode="HTML", reply_markup=result_keyboard(info["cid"], info["sid"], info["tid"]))
    except Exception as e:
        logger.error(f"final fail: {e}")


def get_review(uid, context):
    return context.bot_data.get("last_review", {}).get(uid)
