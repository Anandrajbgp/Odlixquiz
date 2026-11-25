import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import database as dbm
from keyboards import cat_inline, sub_inline, admin_home_panel, admin_stats_line, get_test_qtime, fmt_qtime
import live as lvm
from live import parse_schedule_time

async def live_menu(update, context):
    q = update.callback_query
    if lvm.is_live_active():
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ LIVE Roko", callback_data="adm:livestop")]])
        await q.message.reply_text(lvm.live_status_text() + "\nNeeche button se roko ya /livestop bhejo.",
                                    reply_markup=kb, parse_mode="HTML")
    else:
        context.user_data["astate"] = {"step": "pick_cat_for_live"}
        await q.message.reply_text("🔴 <b>Kis category ka test LIVE bhejna hai?</b>\n🔒 = sirf LIVE ke liye (user ko nahi dikhega)",
                                    reply_markup=cat_inline("livecat"), parse_mode="HTML")

async def livestop(update, context):
    q = update.callback_query
    from live import _lv
    lv = _lv()
    if not lv.get("active"):
        await q.message.reply_text("Koi LIVE nahi chal raha.")
    else:
        lv["active"] = False
        dbm.save_data()
        await q.message.reply_text("⏹ LIVE rok diya.")
        try:
            import broadcast as bcm
            await bcm.broadcast_text(context, "⏹ LIVE TEST rok diya gaya.")
        except Exception:
            pass

async def pick_sub_for_live(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("Category nahi mili.")
        return
    if not c.get("subjects"):
        await q.message.reply_text(f"{c['name']} me koi sub-category nahi.")
        return
    st["step"] = "wait_sub_for_live"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(f"🔴 <b>{c['name']}</b> → sub-category chuno:", reply_markup=sub_inline("livesub", cid), parse_mode="HTML")

async def pick_test_for_live(update, context, cid, sid):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("Sub-category nahi mili.")
        return
    tests = s.get("tests", {}) or {}
    if not tests:
        await q.message.reply_text("Isme koi test nahi.")
        return
    def sortkey(item):
        tid, t = item
        m = re.search(r"(\d+)", t.get("title", "") or "")
        return (int(m.group(1)) if m else 9999, t.get("title", ""))
    btns = []
    for tid, t in sorted(tests.items(), key=sortkey):
        qt = fmt_qtime(get_test_qtime(t=t))
        btns.append([InlineKeyboardButton(f"🔴 {t.get('title', tid)} ({len(t.get('questions', []))} Q, ⏱ {qt})", callback_data=f"livetest:{cid}:{sid}:{tid}")])
    tbtns = []
    for tid, t in sorted(tests.items(), key=sortkey):
        qt = fmt_qtime(get_test_qtime(t=t))
        tbtns.append([InlineKeyboardButton(f"⏱ {t.get('title', tid)} ({qt}) → time badlo", callback_data=f"qtimepick:{cid}:{sid}:{tid}")])
    await q.message.reply_text("🔴 <b>Kaunsa test LIVE bhejna hai?</b> (dabate hi uske time se jayega)", reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
    await q.message.reply_text("⏱ <b>Purane test ka time badalna ho to chuno:</b>", reply_markup=InlineKeyboardMarkup(tbtns), parse_mode="HTML")

async def start_live_test(update, context, cid, sid, tid):
    q = update.callback_query
    if lvm.is_live_active():
        await q.message.reply_text("Ek LIVE chal raha. /livestop se roko.")
        return
    t = dbm.get_test(cid, sid, tid)
    if not t:
        await q.message.reply_text("Test nahi mila.")
        return
    context.user_data.pop("astate", None)
    use_gap = get_test_qtime(cid, sid, tid)
    await q.message.reply_text(f"🔴 LIVE shuru: <b>{t.get('title')}</b> ({len(t.get('questions', []))} Q, ⏱ {use_gap}s/Q).", parse_mode="HTML")
    lvm.start_live_task(context, cid, sid, tid, None, q.message.chat_id)

async def schedule_menu(update, context):
    q = update.callback_query
    schedules = dbm.db.get("schedules", [])
    nsch = len(schedules)
    txt = (
        "📅 <b>TEST SCHEDULE PANEL</b>\n\n"
        f"Abhi active schedules: <b>{nsch}</b>\n\n"
        "Aap kisi bhi test ko kisi bhi time par schedule kar sakte hain.\n"
        "Chuno aap kya karna chahte hain:"
    )
    btns = [
        [InlineKeyboardButton("➕ Naya Test Schedule Karein", callback_data="adm:schadd")],
        [InlineKeyboardButton(f"📋 Active Schedules Dekhein ({nsch})", callback_data="adm:schlist")],
    ]
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")

async def schadd_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_sch"}
    await q.message.reply_text("📅 <b>Kis category ka test schedule karna hai?</b>", reply_markup=cat_inline("schcat"), parse_mode="HTML")

async def schlist(update, context):
    q = update.callback_query
    schedules = dbm.db.get("schedules", [])
    if not schedules:
        await q.message.reply_text("📅 Koi bhi test schedule nahi hai.\n\nSchedule karne ke liye '➕ Naya Test Schedule Karein' chuno.", parse_mode="HTML")
        return
    lines = ["📅 <b>Active Scheduled Tests:</b>\n"]
    btns = []
    for i, sch in enumerate(schedules):
        try:
            dt = datetime.fromisoformat(sch["run_time"]).strftime("%d-%m-%Y %H:%M")
        except Exception:
            dt = sch.get("run_time", "")
        title = sch.get("title", "Test")
        lines.append(f"{i + 1}. <b>{title}</b> — ⏱ {dt}")
        btns.append([InlineKeyboardButton(f"🗑 Cancel: {title} ({dt})", callback_data=f"adm:schdel:{i}")])
    lines.append("\nKisi schedule ko radd karne ke liye button dabayein ya <code>/cancelschedule [number]</code> command use karein.")
    await q.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")

async def pick_sub_for_sch(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("Category nahi mili.")
        return
    if not c.get("subjects"):
        await q.message.reply_text(f"{c['name']} me koi sub-category nahi.")
        return
    st["step"] = "wait_sub_for_sch"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(f"📅 <b>{c['name']}</b> → sub-category chuno:", reply_markup=sub_inline("schsub", cid), parse_mode="HTML")

async def pick_test_for_sch(update, context, cid, sid):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("Sub-category nahi mili.")
        return
    tests = s.get("tests", {}) or {}
    if not tests:
        await q.message.reply_text("Isme koi test nahi.")
        return
    def sortkey(item):
        tid, t = item
        m = re.search(r"(\d+)", t.get("title", "") or "")
        return (int(m.group(1)) if m else 9999, t.get("title", ""))
    btns = []
    for tid, t in sorted(tests.items(), key=sortkey):
        btns.append([InlineKeyboardButton(f"📅 {t.get('title', tid)} ({len(t.get('questions', []))} Qs)", callback_data=f"schtest:{cid}:{sid}:{tid}")])
    await q.message.reply_text("📅 <b>Kaunsa test schedule karna hai?</b>", reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")

async def prompt_schedule_time(update, context, cid, sid, tid):
    q = update.callback_query
    t = dbm.get_test(cid, sid, tid)
    if not t:
        await q.message.reply_text("Test nahi mila.")
        return
    context.user_data["astate"] = {"step": "wait_schedule_time", "cid": cid, "sid": sid, "tid": tid}
    await q.message.reply_text(
        f"📅 <b>'{t.get('title')}' schedule karne ke liye Time bhejo:</b>\n\n"
        "Format:\n"
        "1. <code>YYYY-MM-DD HH:MM</code> (Jaise: <code>2025-05-15 18:30</code>)\n"
        "2. <code>HH:MM</code> (Jaise: <code>18:30</code> - aaj/kal ke liye)\n\n"
        "<i>Radd karne ke liye /cancel bhejo.</i>",
        parse_mode="HTML"
    )

async def schdel(update, context, idx_str):
    q = update.callback_query
    if idx_str.isdigit():
        idx = int(idx_str)
        schedules = dbm.db.get("schedules", [])
        if 0 <= idx < len(schedules):
            removed = schedules.pop(idx)
            dbm.save_data()
            await q.message.reply_text(f"🗑️ Schedule radd kar diya gaya: <b>{removed.get('title')}</b>", parse_mode="HTML")
        else:
            await q.message.reply_text("❌ Galat schedule number.")

async def process_schedule_time(update, context, txt, st):
    if txt == "/cancel":
        context.user_data.pop("astate", None)
        t_msg, k_msg = admin_home_panel(admin_stats_line())
        await update.message.reply_text(f"❌ Schedule karna radd kar diya gaya.\n\n{t_msg}", reply_markup=k_msg, parse_mode="HTML")
        return True

    run_dt = parse_schedule_time(txt)
    if not run_dt:
        await update.message.reply_text(
            "❌ <b>Galat time format!</b>\n"
            "Kripya <code>YYYY-MM-DD HH:MM</code> (ex: <code>2025-05-15 18:30</code>) ya <code>HH:MM</code> (ex: <code>18:30</code>) format me time bhejo ya /cancel karo.",
            parse_mode="HTML"
        )
        return True

    cid = st["cid"]
    sid = st["sid"]
    tid = st["tid"]
    t = dbm.get_test(cid, sid, tid)
    title = t.get("title", "Test") if t else "Test"

    schedule_item = {
        "cid": cid,
        "sid": sid,
        "tid": tid,
        "title": title,
        "run_time": run_dt.isoformat(),
        "admin_chat_id": update.effective_chat.id,
    }

    dbm.db.setdefault("schedules", []).append(schedule_item)
    dbm.save_data()
    context.user_data.pop("astate", None)

    t_msg, k_msg = admin_home_panel(admin_stats_line())
    await update.message.reply_text(
        f"✅ <b>Test Successfully Schedule Ho Gaya!</b>\n\n"
        f"📝 Test: <b>{title}</b>\n"
        f"⏰ Scheduled Time: <b>{run_dt.strftime('%d-%m-%Y %H:%M')}</b>\n\n"
        f"Tay samay par bot ise live kar dega.\n\n{t_msg}",
        reply_markup=k_msg,
        parse_mode="HTML"
    )
    return True
