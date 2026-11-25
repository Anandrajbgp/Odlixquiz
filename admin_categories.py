import database as dbm
from keyboards import cat_inline, sub_inline, confirm_delete_keyboard, admin_home_panel, admin_stats_line

async def pick_delcat(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_delcat"}
    await q.message.reply_text("📂 Kaunsi category delete karni hai? (uske andar sab sub + test ud jayenge)", reply_markup=cat_inline("delcat"))

async def pick_delsub(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_delsub"}
    await q.message.reply_text("📁 Kis category ki sub-category delete karni hai?", reply_markup=cat_inline("delsubcat"))

async def addcat_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "wait_cat_name"}
    await q.message.reply_text("📂 <b>Nayi category ka naam bhejo</b> (jaise RRB, SSC, 12th):", parse_mode="HTML")

async def addsub_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_sub"}
    await q.message.reply_text("📁 Kis category me sub-category banana hai?", reply_markup=cat_inline("asub"))

async def hidecat_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_hide"}
    await q.message.reply_text("👁 <b>Kis category ko LIVE (hidden) / normal karna hai?</b>\n🔒 laga = user ko nahi dikhega, sirf /live se jayega.", reply_markup=cat_inline("hidecat"), parse_mode="HTML")

async def process_addcat_text(update, context, txt):
    if not txt or len(txt) < 2:
        await update.message.reply_text("❌ Naam chhota hai. Dobara bhejo.")
        return True
    cid = dbm.new_id("c", "cat")
    dbm.db["categories"][cid] = {"name": txt[:60], "subjects": {}, "hidden": False}
    dbm.save_data()
    context.user_data.pop("astate", None)
    t2, k2 = admin_home_panel(admin_stats_line())
    await update.message.reply_text(
        f"✅ Category <b>'{txt}'</b> ban gayi!\nAb 📁 Sub-category dabake usme subject banao.\n\n{t2}",
        reply_markup=k2, parse_mode="HTML")
    return True

async def process_addsub_text(update, context, txt, st):
    c = dbm.get_cat(st["cid"])
    if not c:
        context.user_data.pop("astate", None)
        await update.message.reply_text("❌ Category nahi mili.")
        return True
    if not txt or len(txt) < 2:
        await update.message.reply_text("❌ Naam chhota hai. Dobara bhejo.")
        return True
    sid = dbm.new_id("s", "sub")
    c.setdefault("subjects", {})[sid] = {"name": txt[:60], "pdfs": [], "tests": {}}
    dbm.save_data()
    context.user_data.pop("astate", None)
    t3, k3 = admin_home_panel(admin_stats_line())
    await update.message.reply_text(
        f"✅ Sub-category <b>'{txt}'</b> → {c['name']} me ban gayi!\n"
        f"Ab 📄 PDF se Test dabake usme Test 1, 2... banao.\n\n{t3}",
        reply_markup=k3, parse_mode="HTML")
    return True

async def confirm_del_cat(update, context, cid):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("❌ Category nahi mili.")
        return
    nsub = len(c.get("subjects", {}))
    ntest = sum(len(s.get("tests", {})) for s in c.get("subjects", {}).values())
    context.user_data.pop("astate", None)
    await q.message.reply_text(
        f"⚠️ <b>'{c['name']}'</b> delete kar dun?\nUsme {nsub} sub-category + {ntest} test hain — sab ud jayega!",
        reply_markup=confirm_delete_keyboard("cat", cid), parse_mode="HTML")

async def pick_sub_for_delsub(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("❌ Category nahi mili.")
        return
    if not c.get("subjects"):
        await q.message.reply_text(f"❌ {c['name']} me koi sub-category nahi.")
        return
    st["step"] = "pick_sub_for_delsub"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(
        f"📁 <b>{c['name']}</b> → kaunsi sub-category delete karni hai?",
        reply_markup=sub_inline("delsub", cid), parse_mode="HTML")

async def confirm_del_sub(update, context, cid, sid):
    q = update.callback_query
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    ntest = len(s.get("tests", {}))
    context.user_data.pop("astate", None)
    await q.message.reply_text(
        f"⚠️ <b>'{s['name']}'</b> ({c['name']}) delete kar dun?\nUsme {ntest} test hain — sab ud jayega!",
        reply_markup=confirm_delete_keyboard("sub", cid, sid), parse_mode="HTML")

async def execute_del_cat(update, context, cid):
    q = update.callback_query
    c = dbm.get_cat(cid)
    name = c["name"] if c else cid
    if cid in dbm.db.get("categories", {}):
        del dbm.db["categories"][cid]
        dbm.save_data()
        t, k = admin_home_panel(admin_stats_line())
        await q.message.reply_text(f"🗑 Category <b>'{name}'</b> delete ho gayi.\n\n{t}", reply_markup=k, parse_mode="HTML")
    else:
        await q.message.reply_text("❌ Category nahi mili.")
    context.user_data.pop("astate", None)

async def execute_del_sub(update, context, cid, sid):
    q = update.callback_query
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    name = s["name"] if s else sid
    if c and sid in c.get("subjects", {}):
        del c["subjects"][sid]
        dbm.save_data()
        t, k = admin_home_panel(admin_stats_line())
        await q.message.reply_text(f"🗑 Sub-category <b>'{name}'</b> delete ho gayi.\n\n{t}", reply_markup=k, parse_mode="HTML")
    else:
        await q.message.reply_text("❌ Sub-category nahi mili.")
    context.user_data.pop("astate", None)

async def toggle_hide_cat(update, context, cid):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("Category nahi mili.")
        return
    c["hidden"] = not c.get("hidden", False)
    dbm.save_data()
    st2 = "🔒 LIVE-hidden (user ko nahi dikhega)" if c["hidden"] else "👁 Normal (user ko dikhega)"
    await q.message.reply_text(f"<b>{c['name']}</b> ab: {st2}\nAur badalna ho to dobara chuno.",
                                reply_markup=cat_inline("hidecat"), parse_mode="HTML")

async def pick_sub_for_addsub(update, context, cid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    if not c:
        await q.message.reply_text("❌ Category nahi mili.")
        return
    st["step"] = "wait_sub_name"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(f"📁 <b>{c['name']}</b> → sub-category ka naam bhejo:", parse_mode="HTML")
