"""User handlers - home panel, commands, callbacks, history, PDFs, review."""
import logging

from telegram import ReplyKeyboardRemove

import database as dbm
import quiz
from config import ADMIN_ID, HISTORY_LIMIT
from keyboards import (
    admin_home_panel, admin_stats_line, breadcrumb, cat_inline, edit_or_send,
    leaderboard_text, pdf_list_inline, review_keyboard, review_text,
    sub_inline, test_inline, user_home_panel,
)

logger = logging.getLogger(__name__)


async def start_or_menu(update, context):
    uid = update.effective_user.id
    context.user_data.pop("astate", None)
    if uid == ADMIN_ID:
        txt, kb = admin_home_panel(admin_stats_line())
        await update.message.reply_text(
            txt,
            reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "🏠 Home",
            reply_markup=user_home_panel(uid), parse_mode="HTML")


async def cmd_home(update, context):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        txt, kb = admin_home_panel(admin_stats_line())
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "🏠 Home",
            reply_markup=user_home_panel(uid), parse_mode="HTML")


async def cmd_test(update, context):
    if not dbm.db.get("categories"):
        await update.message.reply_text("No categories available — admin will add soon.")
        return
    await update.message.reply_text(
        "📂 <b>Choose Category:</b>", reply_markup=cat_inline("browse"), parse_mode="HTML")


async def cmd_leaderboard(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(
        leaderboard_text(), reply_markup=user_home_panel(uid), parse_mode="HTML")


async def cmd_cancel(update, context):
    uid = update.effective_user.id
    context.user_data.pop("astate", None)
    try:
        import quiz as _qz
        _qz.cancel_live(uid, context)
    except Exception:
        pass
    if uid == ADMIN_ID:
        from keyboards import admin_home_panel, admin_stats_line
        txt, kb = admin_home_panel(admin_stats_line())
        await update.message.reply_text("Cancelled.", reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "Cancelled. Use /start to go back home.",
            reply_markup=user_home_panel(uid))


async def cmd_admin(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    txt, kb = admin_home_panel(admin_stats_line())
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def show_history(update, context):
    h = dbm.get_history(update.effective_user.id)
    if not h:
        await update.message.reply_text("📜 Abhi koi test history nahi hai. Pehle test do!")
        return
    lines = []
    for e in h[-HISTORY_LIMIT:][::-1]:
        lines.append(
            f"{e.get('date', '')} | {e.get('cat', '')}/{e.get('sub', '')} | "
            f"{e.get('test', '')} → {e.get('score')}/{e.get('total')}")
    best = max(x["score"] for x in h)
    uid = update.effective_user.id
    await update.message.reply_text(
        f"📜 Last {len(lines)} tests (Best: {best}):\n" + "\n".join(lines),
        reply_markup=user_home_panel(uid))


async def history_text(uid):
    h = dbm.get_history(uid)
    if not h:
        return "📜 Abhi koi history nahi. Pehle test do!"
    lines = []
    for e in h[-HISTORY_LIMIT:][::-1]:
        lines.append(
            f"{e.get('date', '')} | {e.get('cat', '')}/{e.get('sub', '')} | "
            f"{e.get('test', '')} → {e.get('score')}/{e.get('total')}")
    best = max(x["score"] for x in h)
    return f"📜 <b>Last {len(lines)} (Best: {best}):</b>\n" + "\n".join(lines)


async def handle_text_buttons(update, context):
    msg = update.message
    text = ((msg.text or msg.caption) or "").strip()
    uid = update.effective_user.id
    # /send ya Broadcast mode: admin ka agla message sabko copy
    if uid == ADMIN_ID and context.user_data.get("astate", {}).get("step") == "wait_broadcast_msg":
        import broadcast as bcm
        context.user_data.pop("astate", None)
        ok, fail, errs = await bcm.broadcast_copy(update, context)
        rep = f"📢 Broadcast: {ok} sent, {fail} fail."
        if errs:
            rep += "\n" + "\n".join(errs[:5])
        try:
            await msg.reply_text(rep)
        except Exception:
            pass
        return
    if uid == ADMIN_ID and context.user_data.get("astate"):
        from handlers_admin import admin_text_step
        if await admin_text_step(update, context):
            return
    if text == "⚙️ Admin Panel" and uid == ADMIN_ID:
        from handlers_admin import open_admin_panel_chat
        await open_admin_panel_chat(update, context)
        return
    if text == "📝 Test Do":
        await cmd_test(update, context)
        return
    if text == "📜 History":
        await show_history(update, context)
        return
    if text == "❌ Cancel":
        await cmd_cancel(update, context)
        return
    if text in ("📚 PDFs", "➕ Add Category", "📁 Add Subject", "📝 Add Test",
               "📄 PDF se Test", "📤 Upload PDFs", "📊 Stats"):
        if uid == ADMIN_ID:
            await cmd_admin(update, context)
        else:
            await cmd_home(update, context)
        return
    await start_or_menu(update, context)


async def on_callback(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data or ""
    st = context.user_data.get("astate", {})
    if data == "noop":
        return
    if data == "home:main":
        context.user_data.pop("astate", None)
        if uid == ADMIN_ID:
            txt, kb = admin_home_panel(admin_stats_line())
            await edit_or_send(q, txt, kb)
        else:
            await edit_or_send(
                q, "🏠 Home",
                user_home_panel(uid))
        return
    if data == "home:cats":
        if not dbm.db["categories"]:
            await edit_or_send(q, "No categories available.", user_home_panel(uid))
            return
        from keyboards import nav_row
        from telegram import InlineKeyboardMarkup
        kb = cat_inline("browse")
        rows = list(kb.inline_keyboard) + [nav_row()]
        await edit_or_send(q, "📂 <b>Category chuno:</b>", InlineKeyboardMarkup(rows))
        return
    if data == "home:pdfcats":
        if not dbm.db["categories"]:
            await edit_or_send(q, "No categories available.", user_home_panel(uid))
            return
        from keyboards import nav_row
        from telegram import InlineKeyboardMarkup
        kb = cat_inline("pdfcat")
        rows = list(kb.inline_keyboard) + [nav_row()]
        await edit_or_send(q, "📚 <b>PDFs ke liye category chuno:</b>", InlineKeyboardMarkup(rows))
        return
    if data == "home:history":
        await edit_or_send(q, await history_text(uid), user_home_panel(uid))
        return
    if data == "home:board":
        await edit_or_send(q, leaderboard_text(), user_home_panel(uid))
        return
    if data.startswith("page:"):
        _, prefix, pagestr = data.split(":")
        try:
            page = int(pagestr)
        except ValueError:
            page = 0
        from keyboards import nav_row
        from telegram import InlineKeyboardMarkup
        kb = cat_inline(prefix, page)
        rows = list(kb.inline_keyboard) + [nav_row()]
        await edit_or_send(q, "📂 <b>Category chuno:</b>", InlineKeyboardMarkup(rows))
        return
    if data.startswith("adm:"):
        if uid != ADMIN_ID:
            await q.answer("Admin only.", show_alert=True)
            return
        from handlers_admin import admin_panel_callback
        # livecat/hidecat/livetest yahin handle honge (hidden cat par bhi)
        handled = await admin_panel_callback(update, context, data)
        if handled is not False:
            return
    if data.startswith(("livecat:", "livesub:", "livetest:", "hidecat:", "qtime:", "qtimechg:", "qtimepick:")):
        if uid != ADMIN_ID:
            await q.answer("Admin only.", show_alert=True)
            return
        from handlers_admin import admin_callback
        try:
            await admin_callback(update, context, data, st)
        except Exception as e:
            import logging as _lg
            _lg.getLogger(__name__).error(f"live/hide callback fail {data}: {e}", exc_info=e)
            try:
                await q.message.reply_text(f"❌ LIVE me error: {e}\nDebug: {data}")
            except Exception:
                pass
        return
    if uid != ADMIN_ID and (
        data.startswith("livecat:") or data.startswith("livesub:") or data.startswith("livetest:")
        or data.startswith("hidecat:")
    ):
        await q.answer("Admin only.", show_alert=True)
        return
    if uid != ADMIN_ID and data.startswith(("browse:", "bsub:", "tsub:", "start:")):
        try:
            parts = data.split(":")
            chk = dbm.get_cat(parts[1]) if len(parts) > 1 else None
            if chk and chk.get("hidden"):
                await q.answer("Ye test LIVE par hoga.", show_alert=True)
                return
        except Exception:
            pass
    if data.startswith("browse:"):
        cid = data.split(":")[1]
        c = dbm.get_cat(cid)
        if c:
            await edit_or_send(
                q, f"{breadcrumb(c['name'])}\n📁 <b>Subject chuno:</b>",
                sub_inline("bsub", cid))
        return
    if data.startswith("bsub:"):
        parts = data.split(":")
        if len(parts) == 3:
            # bsub:{cid}:{sid} -> is sub-category ke tests dikhao
            _, cid, sid = parts
            c = dbm.get_cat(cid)
            s = dbm.get_sub(cid, sid)
            if c and s:
                await edit_or_send(
                    q, f"{breadcrumb(c['name'], s['name'])}\n📝 <b>Test chuno:</b>",
                    test_inline(cid, sid))
        elif len(parts) == 2:
            # bsub:{cid} -> is category ki sub-categories dikhao (back from tests)
            cid = parts[1]
            c = dbm.get_cat(cid)
            if c:
                await edit_or_send(
                    q, f"{breadcrumb(c['name'])}\n📁 <b>Subject chuno:</b>",
                    sub_inline("bsub", cid))
        return
    if data.startswith("tsub:"):
        _, cid, sid = data.split(":")
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        if c and s:
            if not s.get("tests"):
                await edit_or_send(
                    q, f"{breadcrumb(c['name'], s['name'])}\nIs subject me koi test nahi.",
                    test_inline(cid, sid))
                return
            await edit_or_send(
                q, f"{breadcrumb(c['name'], s['name'])}\n📝 <b>Test chuno:</b>",
                test_inline(cid, sid))
        return
    if data.startswith("start:"):
        _, cid, sid, tid = data.split(":")
        try:
            await q.message.reply_text("🚀 Test starting...")
        except Exception:
            pass
        await quiz.begin_test(q.message.chat_id, uid, cid, sid, tid, context)
        return
    if data == "quiz:stop":
        paused = quiz.pause_quiz(uid, context)
        if paused:
            try:
                await q.message.reply_text(
                    f"⏸ Quiz paused.\n"
                    f"Progress: {paused['done']}/{paused['total']} questions\n"
                    f"Score so far: {paused['score']}\n"
                    f"Use Home to resume later.",
                    reply_markup=user_home_panel(uid), parse_mode="HTML")
            except Exception:
                pass
        else:
            await edit_or_send(q, "❌ No active quiz to pause.", user_home_panel(uid))
        return
    if data == "quiz:resume":
        paused = quiz.resume_quiz(uid, context)
        if not paused:
            await edit_or_send(q, "❌ No paused quiz to resume.", user_home_panel(uid))
            return
        quiz.clear_paused(uid, context)
        # Set up live state at saved position
        live = context.bot_data.setdefault("live", {})[uid] = {
            "score": paused["score"], "done": paused["done"],
            "total": paused["total"], "cid": paused["cid"],
            "sid": paused["sid"], "tid": paused["tid"], "title": paused["title"],
        }
        # Send the saved question index
        t = dbm.get_test(paused["cid"], paused["sid"], paused["tid"])
        if t and paused["qi"] < len(t["questions"]):
            try:
                stop_msg_id = context.user_data.get("stop_msg_id")
                msg = await quiz.send_q(q.message.chat_id, uid, paused["cid"],
                                        paused["sid"], paused["tid"], paused["qi"],
                                        context, stop_msg_id=stop_msg_id)
                from quiz import active_polls
                from datetime import datetime
                active_polls[msg.poll.id] = {
                    "cid": paused["cid"], "sid": paused["sid"], "tid": paused["tid"],
                    "qi": paused["qi"], "uid": uid,
                    "start_time": datetime.now(),
                }
                await q.message.reply_text(
                    f"▶️ Quiz resumed.\n"
                    f"Progress: {paused['done']}/{paused['total']} questions\n"
                    f"Score so far: {paused['score']}",
                    parse_mode="HTML")
            except Exception as e:
                logger.error(f"resume send_q fail: {e}")
        else:
            await edit_or_send(q, "❌ Resume failed — test data missing.", user_home_panel(uid))
        return
    if data.startswith("rev:"):
        _, idxstr, cid, sid, tid = data.split(":")
        try:
            idx = int(idxstr)
        except ValueError:
            idx = 0
        rev = quiz.get_review(uid, context)
        if not rev or not rev.get("details"):
            await edit_or_send(q, "❌ Review expired. Take the test again.",
                               user_home_panel(uid))
            return
        details = rev["details"]
        idx = max(0, min(idx, len(details) - 1))
        await edit_or_send(
            q, review_text(details[idx], idx, len(details)),
            review_keyboard(idx, len(details), cid, sid, tid))
        return
    if data.startswith("pdfcat:"):
        cid = data.split(":")[1]
        c = dbm.get_cat(cid)
        if c:
            await edit_or_send(
                q, f"{breadcrumb(c['name'])}\n📚 <b>Subject chuno (PDFs):</b>",
                sub_inline("pdfsub", cid))
        return
    if data.startswith("pdfsub:"):
        _, cid, sid = data.split(":")
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        if c and s:
            kb = pdf_list_inline(cid, sid, back_cb=f"pdfcat:{cid}")
            await edit_or_send(
                q, f"{breadcrumb(c['name'], s['name'])}\n📚 <b>PDF chuno:</b>", kb)
        return
    if data.startswith("pdfs:"):
        _, cid, sid = data.split(":")
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        if c and s:
            kb = pdf_list_inline(cid, sid, back_cb=f"tsub:{cid}:{sid}")
            await edit_or_send(
                q, f"{breadcrumb(c['name'], s['name'])}\n📚 <b>Study PDFs:</b>", kb)
        return
    if data.startswith("pdf:"):
        _, cid, sid, istr = data.split(":")
        try:
            i = int(istr)
        except ValueError:
            return
        s = dbm.get_sub(cid, sid)
        if s and 0 <= i < len(s.get("pdfs", []) or []):
            p = s["pdfs"][i]
            try:
                await context.bot.send_document(
                    chat_id=q.message.chat_id, document=p["file_id"],
                    caption=f"📄 {p.get('file_name', '')}")
            except Exception as e:
                logger.error(f"pdf send fail: {e}")
                await q.message.reply_text("❌ PDF bhejne me error.")
        return
    if data == "delmenu":
        from keyboards import delete_menu
        await edit_or_send(q, "🗑 <b>Kya delete karna hai?</b>", delete_menu())
        return
    if data.startswith("delback:"):
        # format: delback:<menu-cb>:... -> wapas usi list pe
        rest = data.split(":", 1)[1] if ":" in data else ""
        if rest.startswith("delsub:"):
            cid = rest.split(":")[1]
            c = dbm.get_cat(cid)
            if c:
                await edit_or_send(
                    q, f"📁 <b>{c['name']}</b> → kaunsi sub-category delete karni hai?",
                    sub_inline("delsub", cid))
        elif rest.startswith("deltest:"):
            _, cid, sid = rest.split(":")
            s = dbm.get_sub(cid, sid)
            if s:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                btns = []
                for tid, t in s.get("tests", {}).items():
                    btns.append([InlineKeyboardButton(
                        f"🗑 {t.get('title', tid)} ({len(t.get('questions', []))} Qs)",
                        callback_data=f"deltest:{cid}:{sid}:{tid}")])
                await edit_or_send(q, "📝 Kaunsa test delete karna hai?",
                                   InlineKeyboardMarkup(btns))
        else:
            from keyboards import delete_menu
            await edit_or_send(q, "🗑 <b>Kya delete karna hai?</b>", delete_menu())
        return
    if uid == ADMIN_ID and (
        data.startswith("asub:") or data.startswith("atest:") or data.startswith("tsub2:")
        or data.startswith("apdf:") or data.startswith("psub2:")
        or data.startswith("atestpdf:") or data.startswith("tsubpdf:")
        or data.startswith("delcat:") or data.startswith("delsubcat:")
        or data.startswith("delsub:") or data.startswith("deltestcat:")
        or data.startswith("deltestsub:") or data.startswith("deltest:")
        or data.startswith("deldo:del:")
        or data.startswith("hidecat:") or data.startswith("livecat:")
        or data.startswith("livesub:") or data.startswith("livetest:")
        or data.startswith("qtime:") or data.startswith("qtimechg:") or data.startswith("qtimepick:")
    ):
        from handlers_admin import admin_callback
        await admin_callback(update, context, data, st)
        return
    if data.startswith("back:"):
        prefix = data.split(":", 1)[1] if ":" in data else ""
        base = "browse" if prefix in ("browse", "bsub", "tsub") else (prefix or "browse")
        from keyboards import nav_row
        from telegram import InlineKeyboardMarkup
        kb = cat_inline(base)
        rows = list(kb.inline_keyboard) + [nav_row()]
        await edit_or_send(q, "📂 <b>Category:</b>", InlineKeyboardMarkup(rows))
        return
