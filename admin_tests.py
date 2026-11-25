import database as dbm
from keyboards import cat_inline, sub_inline, confirm_delete_keyboard, admin_home_panel, admin_stats_line, qtime_keyboard, set_test_qtime, fmt_qtime, get_test_qtime
from parser_utils import Q_FMT, parse_questions
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def pick_deltest(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_deltest"}
    await q.message.reply_text("📝 Kis category ka test delete karna hai?", reply_markup=cat_inline("deltestcat"))

async def addtest_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_test"}
    await q.message.reply_text("📝 Kis category me text se Test banana hai?", reply_markup=cat_inline("atest"))

async def pick_sub_for_deltest(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("❌ Category nahi mili.")
        return
    if not c.get("subjects"):
        await q.message.reply_text(f"❌ {c['name']} me koi sub-category nahi.")
        return
    st["step"] = "pick_sub_for_deltest"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(
        f"📝 <b>{c['name']}</b> → kis sub-category ka test delete karna hai?",
        reply_markup=sub_inline("deltestsub", cid), parse_mode="HTML")

async def pick_test_for_del(update, context, cid, sid, st):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    if not s.get("tests"):
        await q.message.reply_text(f"❌ {s['name']} me koi test nahi.")
        return
    st["step"] = "pick_test_for_del"
    st["cid"] = cid
    st["sid"] = sid
    context.user_data["astate"] = st
    btns = []
    for tid, t in s.get("tests", {}).items():
        btns.append([InlineKeyboardButton(
            f"🗑 {t.get('title', tid)} ({len(t.get('questions', []))} Qs)",
            callback_data=f"deltest:{cid}:{sid}:{tid}")])
    await q.message.reply_text(
        "📝 Kaunsa test delete karna hai?",
        reply_markup=InlineKeyboardMarkup(btns))

async def confirm_del_test(update, context, cid, sid, tid):
    q = update.callback_query
    t = dbm.get_test(cid, sid, tid)
    if not t:
        await q.message.reply_text("❌ Test nahi mila.")
        return
    context.user_data.pop("astate", None)
    await q.message.reply_text(
        f"⚠️ <b>'{t['title']}'</b> ({len(t.get('questions', []))} Qs) delete kar dun?",
        reply_markup=confirm_delete_keyboard("test", cid, sid, tid), parse_mode="HTML")

async def execute_del_test(update, context, cid, sid, tid):
    q = update.callback_query
    s = dbm.get_sub(cid, sid)
    t0 = dbm.get_test(cid, sid, tid)
    name = t0["title"] if t0 else tid
    if s and tid in s.get("tests", {}):
        del s["tests"][tid]
        dbm.save_data()
        t_msg, k_msg = admin_home_panel(admin_stats_line())
        await q.message.reply_text(f"🗑 Test <b>'{name}'</b> delete ho gaya.\n\n{t_msg}", reply_markup=k_msg, parse_mode="HTML")
    else:
        await q.message.reply_text("❌ Test nahi mila.")
    context.user_data.pop("astate", None)

async def pick_sub_for_test(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("❌ Category nahi mili.")
        return
    if not c.get("subjects"):
        await q.message.reply_text(
            f"❌ <b>{c['name']}</b> me koi sub-category nahi. Pehle 📁 Sub-category banao.",
            parse_mode="HTML")
        return
    st["step"] = "wait_sub_for_test"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(
        f"📂 <b>{c['name']}</b> → sub-category chuno:",
        reply_markup=sub_inline("tsub2", cid),
        parse_mode="HTML")

async def prompt_test_body(update, context, cid, sid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    st.update({"step": "wait_test_body_simple", "cid": cid, "sid": sid})
    context.user_data["astate"] = st
    n = dbm.next_test_number_in(cid, sid)
    await q.message.reply_text(
        f"✅ <b>{c['name']} › {s['name']}</b> select!\n"
        f"Ab Q-format text paste karo → <b>Test {n}</b> ban jayega.\n"
        f"<code>{Q_FMT}</code>",
        parse_mode="HTML")

async def process_test_body(update, context, txt, st):
    qs = parse_questions(txt)
    if not qs:
        await update.message.reply_text(
            "❌ Valid Q nahi mila. Har Q is format me bhejo:\n"
            f"<code>{Q_FMT}</code>", parse_mode="HTML")
        return True
    s = dbm.get_sub(st["cid"], st["sid"])
    if not s:
        context.user_data.pop("astate", None)
        await update.message.reply_text("❌ Sub-category nahi mili.")
        return True
    n = dbm.next_test_number_in(st["cid"], st["sid"])
    title = f"Test {n}"
    tid = dbm.new_id("t", "test")
    s["tests"][tid] = {"title": title, "questions": qs, "qtime": 30}
    dbm.save_data()
    context.user_data.pop("astate", None)
    t4, k4 = admin_home_panel(admin_stats_line())
    await update.message.reply_text(
        f"✅ <b>{title}</b> save! {len(qs)} Qs.\n\n"
        f"⏱ <b>Har Q par kitna time?</b> (LIVE channel + personal dono me yahi lagega)\n"
        f"Neeche dabao ya /cancel (30s default):",
        reply_markup=qtime_keyboard("qtime", st["cid"], st["sid"], tid), parse_mode="HTML")
    context.user_data["astate"] = {"step": "wait_qtime", "cid": st["cid"], "sid": st["sid"], "tid": tid}
    return True

async def qtime_set(update, context, cid, sid, tid, sec):
    q = update.callback_query
    try:
        sec_i = int(sec)
    except Exception:
        sec_i = 30
    if set_test_qtime(cid, sid, tid, sec_i):
        t = dbm.get_test(cid, sid, tid)
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        cname = c.get("name", "") if c else ""
        sname = s.get("name", "") if s else ""
        await q.message.reply_text(
            f"⏱ <b>{t.get('title')}</b> → {cname} › {sname}: har Q par <b>{fmt_qtime(sec_i)}</b> set!\n"
            f"LIVE channel me har {sec_i} sec me ek Q jayega. Personal me bhi yahi timer lagega.",
            parse_mode="HTML")
    else:
        await q.message.reply_text("❌ Test nahi mila.")
    context.user_data.pop("astate", None)
    t5, k5 = admin_home_panel(admin_stats_line())
    await q.message.reply_text(t5, reply_markup=k5, parse_mode="HTML")

async def qtime_change(update, context, cid, sid, tid, sec):
    q = update.callback_query
    try:
        sec_i = int(sec)
    except Exception:
        sec_i = 30
    if set_test_qtime(cid, sid, tid, sec_i):
        t = dbm.get_test(cid, sid, tid)
        await q.message.reply_text(
            f"⏱ <b>{t.get('title')}</b> ka time ab <b>{fmt_qtime(sec_i)}</b>/Q!",
            parse_mode="HTML")
    else:
        await q.message.reply_text("❌ Test nahi mila.")
    context.user_data.pop("astate", None)

async def qtime_pick(update, context, cid, sid, tid):
    q = update.callback_query
    t = dbm.get_test(cid, sid, tid)
    if not t:
        await q.message.reply_text("❌ Test nahi mila.")
        return
    await q.message.reply_text(
        f"⏱ <b>{t.get('title')}</b> — abhi {fmt_qtime(get_test_qtime(t=t))}/Q. Naya time chuno:",
        reply_markup=qtime_keyboard("qtimechg", cid, sid, tid), parse_mode="HTML")
