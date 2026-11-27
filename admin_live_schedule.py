"""Admin live & schedule test management handlers."""
import logging
from datetime import datetime, timezone, timedelta
import database as dbm
import live as lvm
from keyboards import cat_inline, sub_inline, test_inline, admin_home_panel, admin_stats_line
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def live_menu(update, context):
    q = update.callback_query
    txt = lvm.live_status_text()
    if lvm.is_live_active():
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ LIVE Roko", callback_data="adm:livestop")],
            [InlineKeyboardButton("🏠 Admin Home", callback_data="home:main")]
        ])
        await q.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        context.user_data["astate"] = {"step": "pick_cat_for_live"}
        await q.message.reply_text(
            f"{txt}\n\n<b>LIVE bhejne ke liye category chuno:</b>",
            reply_markup=cat_inline("livecat"),
            parse_mode="HTML"
        )


async def schedule_menu(update, context):
    q = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Naya Schedule Add Karo", callback_data="adm:schadd")],
        [InlineKeyboardButton("📋 Scheduled Tests Dekho", callback_data="adm:schlist")],
        [InlineKeyboardButton("🏠 Admin Home", callback_data="home:main")]
    ])
    await q.message.reply_text(
        "📅 <b>Schedule Test Menu:</b>\nKuch time baad automatic live test chalane ke liye chuno:",
        reply_markup=kb,
        parse_mode="HTML"
    )


async def schadd_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_sch"}
    await q.message.reply_text(
        "📅 <b>Schedule Test ke liye category chuno:</b>",
        reply_markup=cat_inline("schcat"),
        parse_mode="HTML"
    )


async def schlist(update, context):
    q = update.callback_query
    schedules = dbm.db.get("schedules", [])
    if not schedules:
        await q.message.reply_text("📋 Abhi koi scheduled test nahi hai.")
        return
    lines = ["📋 <b>Scheduled Tests List:</b>\n"]
    btns = []
    for idx, sch in enumerate(schedules):
        lines.append(f"{idx + 1}. <b>{sch.get('title', '?')}</b>\n ⏰ {sch.get('run_time', '?')}")
        btns.append([InlineKeyboardButton(f"🗑 Delete #{idx + 1} ({sch.get('title', '?')})", callback_data=f"schdel:{idx}")])
    btns.append([InlineKeyboardButton("🏠 Admin Home", callback_data="home:main")])
    await q.message.reply_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")


async def livestop(update, context):
    q = update.callback_query
    lv = dbm.db.get("live", {})
    title = lv.get("tid", "LIVE")
    lv["active"] = False
    dbm.save_data()
    txt, kb = admin_home_panel(admin_stats_line())
    await q.message.reply_text(f"⏹ <b>LIVE Test roka gaya.</b>\n\n{txt}", reply_markup=kb, parse_mode="HTML")


async def pick_sub_for_live(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c or not c.get("subjects"):
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    st.update({"step": "pick_sub_for_live", "cid": cid})
    context.user_data["astate"] = st
    await q.message.reply_text(f"📂 <b>{c['name']}</b> → sub-category chuno:", reply_markup=sub_inline("livesub", cid), parse_mode="HTML")


async def pick_test_for_live(update, context, cid, sid):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    if not s or not s.get("tests"):
        await q.message.reply_text("❌ Is sub-category me koi test nahi hai.")
        return
    btns = []
    for tid, t in s.get("tests", {}).items():
        btns.append([InlineKeyboardButton(f"🔴 LIVE {t.get('title', tid)} ({len(t.get('questions', []))} Qs)", callback_data=f"livetest:{cid}:{sid}:{tid}")])
    await q.message.reply_text("📝 <b>Kaunsa Test LIVE bhejna hai?</b>", reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")


async def start_live_test(update, context, cid, sid, tid):
    q = update.callback_query
    admin_id = update.effective_user.id
    context.user_data.pop("astate", None)
    lvm.start_live_task(context, cid, sid, tid, None, admin_id)
    await q.message.reply_text("🚀 LIVE Test shuru ho raha hai...")


async def pick_sub_for_sch(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c or not c.get("subjects"):
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    st.update({"step": "pick_sub_for_sch", "cid": cid})
    context.user_data["astate"] = st
    await q.message.reply_text(f"📂 <b>{c['name']}</b> → sub-category chuno:", reply_markup=sub_inline("schsub", cid), parse_mode="HTML")


async def pick_test_for_sch(update, context, cid, sid):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    if not s or not s.get("tests"):
        await q.message.reply_text("❌ Is sub-category me koi test nahi hai.")
        return
    btns = []
    for tid, t in s.get("tests", {}).items():
        btns.append([InlineKeyboardButton(f"📅 Schedule {t.get('title', tid)}", callback_data=f"schtest:{cid}:{sid}:{tid}")])
    await q.message.reply_text("📝 <b>Kaunsa Test Schedule karna hai?</b>", reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")


async def prompt_schedule_time(update, context, cid, sid, tid):
    q = update.callback_query
    t = dbm.get_test(cid, sid, tid)
    if not t:
        await q.message.reply_text("❌ Test nahi mila.")
        return
    context.user_data["astate"] = {"step": "wait_schedule_time", "cid": cid, "sid": sid, "tid": tid}
    IST = timezone(timedelta(hours=5, minutes=30))
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    await q.message.reply_text(
        f"📅 <b>{t.get('title')}</b> Schedule karne ke liye time bhejo:\n\n"
        f"12-hour format: <code>6:30 PM</code> ya <code>06:30 PM</code>\n"
        f"24-hour format: <code>21:30</code> (aaj ya kal ke liye)\n"
        f"Date + time: <code>2026-11-27 6:30 PM</code> ya <code>27-11-2026 6:30 PM</code>\n"
        f"Abhi ka time: <code>{now_str}</code>",
        parse_mode="HTML"
    )


async def schdel(update, context, idx_str):
    q = update.callback_query
    try:
        idx = int(idx_str)
        schedules = dbm.db.get("schedules", [])
        if 0 <= idx < len(schedules):
            removed = schedules.pop(idx)
            dbm.save_data()
            if getattr(context, "job_queue", None) and "sch_id" in removed:
                lvm.remove_test_job(context.job_queue, removed["sch_id"])
            await q.message.reply_text(f"🗑 Schedule <b>'{removed.get('title')}'</b> delete ho gaya.", parse_mode="HTML")
        else:
            await q.message.reply_text("❌ Schedule nahi mila.")
    except Exception as e:
        await q.message.reply_text(f"❌ Error: {e}")


async def process_schedule_time(update, context, txt, st):
    run_dt = lvm.parse_schedule_time(txt)
    if not run_dt:
        await update.message.reply_text("❌ Galat time format. Example: <code>6:30 PM</code> ya <code>21:30</code>", parse_mode="HTML")
        return True
    cid, sid, tid = st.get("cid"), st.get("sid"), st.get("tid")
    t = dbm.get_test(cid, sid, tid)
    if not t:
        context.user_data.pop("astate", None)
        await update.message.reply_text("❌ Test nahi mila.")
        return True
    sch_id = f"{tid}_{int(datetime.now().timestamp())}"
    sch_entry = {
        "sch_id": sch_id,
        "cid": cid, "sid": sid, "tid": tid,
        "title": t.get("title"),
        "run_time": run_dt.isoformat(),
        "admin_chat_id": update.effective_chat.id
    }
    dbm.db.setdefault("schedules", []).append(sch_entry)
    dbm.save_data()
    if getattr(context, "job_queue", None):
        lvm.schedule_test_job(context.job_queue, sch_entry)
    context.user_data.pop("astate", None)
    txt_out, kb_out = admin_home_panel(admin_stats_line())
    await update.message.reply_text(
        f"✅ <b>{t.get('title')}</b> schedule ho gaya!\n⏰ Time: <b>{run_dt.strftime('%d-%m-%Y %I:%M %p')}</b>\n\n{txt_out}",
        reply_markup=kb_out, parse_mode="HTML"
    )
    return True
