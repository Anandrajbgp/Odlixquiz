"""Admin handlers - category, sub-category, PDF se Test."""
import logging

import database as dbm
from keyboards import admin_home_panel, admin_stats_line, cat_inline, sub_inline
from parser_utils import Q_FMT, clean_text, parse_questions, pdf_to_text

logger = logging.getLogger(__name__)


async def open_admin_panel_chat(update, context):
    txt, kb = admin_home_panel(admin_stats_line())
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def admin_panel_callback(update, context, data):
    q = update.callback_query
    act = data.split(":", 1)[1] if ":" in data else ""
    if act == "del":
        from keyboards import delete_menu
        await q.message.reply_text("🗑 <b>Kya delete karna hai?</b>", reply_markup=delete_menu(), parse_mode="HTML")
    elif act == "delcat":
        context.user_data["astate"] = {"step": "pick_cat_for_delcat"}
        await q.message.reply_text("📂 Kaunsi category delete karni hai? (uske andar sab sub + test ud jayenge)", reply_markup=cat_inline("delcat"))
    elif act == "delsub":
        context.user_data["astate"] = {"step": "pick_cat_for_delsub"}
        await q.message.reply_text("📁 Kis category ki sub-category delete karni hai?", reply_markup=cat_inline("delsubcat"))
    elif act == "deltest":
        context.user_data["astate"] = {"step": "pick_cat_for_deltest"}
        await q.message.reply_text("📝 Kis category ka test delete karna hai?", reply_markup=cat_inline("deltestcat"))
    elif act == "addcat":
        context.user_data["astate"] = {"step": "wait_cat_name"}
        await q.message.reply_text("📂 <b>Nayi category ka naam bhejo</b> (jaise RRB, SSC, 12th):", parse_mode="HTML")
    elif act == "addsub":
        context.user_data["astate"] = {"step": "pick_cat_for_sub"}
        await q.message.reply_text("📁 Kis category me sub-category banana hai?", reply_markup=cat_inline("asub"))
    elif act == "addtestpdf":
        context.user_data["astate"] = {"step": "pick_cat_for_testpdf"}
        await q.message.reply_text("📄 Kis category me Test banana hai?", reply_markup=cat_inline("atestpdf"))
    elif act == "addtest":
        context.user_data["astate"] = {"step": "pick_cat_for_test"}
        await q.message.reply_text("📝 Kis category me text se Test banana hai?", reply_markup=cat_inline("atest"))
    elif act == "stats":
        await q.message.reply_text(admin_stats_line(), parse_mode="HTML")
    elif act == "scores":
        from keyboards import leaderboard_text
        await q.message.reply_text(leaderboard_text(), parse_mode="HTML")
    elif act == "allhist":
        hist = dbm.db.get("history", {})
        if not hist:
            await q.message.reply_text("Koi attempt nahi.")
            return
        lines = []
        for uid2, arr in hist.items():
            for e in arr[-3:]:
                lines.append(f"{e.get('name', uid2)} | {e.get('cat','')}/{e.get('sub','')} → {e.get('score')}/{e.get('total')}")
        await q.message.reply_text("Sabki history:\n" + "\n".join(lines[-15:]))


async def admin_text_step(update, context):
    txt = clean_text(update.message.text.strip())
    st = context.user_data.get("astate")
    if not st:
        return False
    step = st.get("step")
    if step == "wait_cat_name":
        if not txt or len(txt) < 2:
            await update.message.reply_text("❌ Naam chhota hai. Dobara bhejo.")
            return True
        cid = dbm.new_id("c", "cat")
        dbm.db["categories"][cid] = {"name": txt[:60], "subjects": {}}
        dbm.save_data()
        context.user_data.pop("astate", None)
        from keyboards import admin_home_panel as ahp, admin_stats_line as asl
        t2, k2 = ahp(asl())
        await update.message.reply_text(
            f"✅ Category <b>'{txt}'</b> ban gayi!\nAb 📁 Sub-category dabake usme subject banao.\n\n{t2}",
            reply_markup=k2, parse_mode="HTML")
        return True
    if step == "wait_sub_name":
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
        from keyboards import admin_home_panel as ahp3, admin_stats_line as asl3
        t3, k3 = ahp3(asl3())
        await update.message.reply_text(
            f"✅ Sub-category <b>'{txt}'</b> → {c['name']} me ban gayi!\n"
            f"Ab 📄 PDF se Test dabake usme Test 1, 2... banao.\n\n{t3}",
            reply_markup=k3, parse_mode="HTML")
        return True
    if step == "wait_test_body_simple":
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
        s["tests"][tid] = {"title": title, "questions": qs}
        dbm.save_data()
        context.user_data.pop("astate", None)
        from keyboards import admin_home_panel as ahp2, admin_stats_line as asl2
        t4, k4 = ahp2(asl2())
        await update.message.reply_text(
            f"✅ <b>{title}</b> save! {len(qs)} Qs.\n\n{t4}",
            reply_markup=k4, parse_mode="HTML")
        return True
    return False


async def admin_callback(update, context, data, st):
    """Category -> sub-category pick flow + delete flow + delete confirm."""
    q = update.callback_query
    # ---- DELETE CONFIRM: pakka udao ----
    if data.startswith("deldo:del:"):
        # format: deldo:del:<kind>:<cid>:<sid>:<tid>
        parts = data.split(":")
        kind = parts[2] if len(parts) > 2 else ""
        cid = parts[3] if len(parts) > 3 else ""
        sid = parts[4] if len(parts) > 4 else ""
        tid = parts[5] if len(parts) > 5 else ""
        from keyboards import admin_home_panel as ahp, admin_stats_line as asl
        if kind == "cat":
            c = dbm.get_cat(cid)
            name = c["name"] if c else cid
            if cid in dbm.db.get("categories", {}):
                del dbm.db["categories"][cid]
                dbm.save_data()
                t, k = ahp(asl())
                await q.message.reply_text(f"🗑 Category <b>'{name}'</b> delete ho gayi.\n\n{t}", reply_markup=k, parse_mode="HTML")
            else:
                await q.message.reply_text("❌ Category nahi mili.")
        elif kind == "sub":
            c = dbm.get_cat(cid)
            s = dbm.get_sub(cid, sid)
            name = s["name"] if s else sid
            if c and sid in c.get("subjects", {}):
                del c["subjects"][sid]
                dbm.save_data()
                t, k = ahp(asl())
                await q.message.reply_text(f"🗑 Sub-category <b>'{name}'</b> delete ho gayi.\n\n{t}", reply_markup=k, parse_mode="HTML")
            else:
                await q.message.reply_text("❌ Sub-category nahi mili.")
        elif kind == "test":
            s = dbm.get_sub(cid, sid)
            t0 = dbm.get_test(cid, sid, tid)
            name = t0["title"] if t0 else tid
            if s and tid in s.get("tests", {}):
                del s["tests"][tid]
                dbm.save_data()
                t, k = ahp(asl())
                await q.message.reply_text(f"🗑 Test <b>'{name}'</b> delete ho gaya.\n\n{t}", reply_markup=k, parse_mode="HTML")
            else:
                await q.message.reply_text("❌ Test nahi mila.")
        else:
            await q.message.reply_text("❌ Samajh nahi aaya.")
        context.user_data.pop("astate", None)
        return
    # ---- DELETE: category chuni ----
    if data.startswith("delcat:"):
        cid = data.split(":")[1]
        c = dbm.get_cat(cid)
        if not c:
            await q.message.reply_text("❌ Category nahi mili.")
            return
        nsub = len(c.get("subjects", {}))
        ntest = sum(len(s.get("tests", {})) for s in c.get("subjects", {}).values())
        from keyboards import confirm_delete_keyboard
        context.user_data.pop("astate", None)
        await q.message.reply_text(
            f"⚠️ <b>'{c['name']}'</b> delete kar dun?\n"
            f"Usme {nsub} sub-category + {ntest} test hain — sab ud jayega!",
            reply_markup=confirm_delete_keyboard("cat", cid), parse_mode="HTML")
        return
    # ---- DELETE: sub ke liye category chuni -> sub chuno ----
    if data.startswith("delsubcat:"):
        cid = data.split(":")[1]
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
        return
    if data.startswith("delsub:"):
        _, cid, sid = data.split(":")
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        if not s:
            await q.message.reply_text("❌ Sub-category nahi mili.")
            return
        ntest = len(s.get("tests", {}))
        from keyboards import confirm_delete_keyboard
        context.user_data.pop("astate", None)
        await q.message.reply_text(
            f"⚠️ <b>'{s['name']}'</b> ({c['name']}) delete kar dun?\n"
            f"Usme {ntest} test hain — sab ud jayega!",
            reply_markup=confirm_delete_keyboard("sub", cid, sid), parse_mode="HTML")
        return
    # ---- DELETE: test ke liye category -> sub -> test ----
    if data.startswith("deltestcat:"):
        cid = data.split(":")[1]
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
        return
    if data.startswith("deltestsub:"):
        _, cid, sid = data.split(":")
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
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        btns = []
        for tid, t in s.get("tests", {}).items():
            btns.append([InlineKeyboardButton(
                f"🗑 {t.get('title', tid)} ({len(t.get('questions', []))} Qs)",
                callback_data=f"deltest:{cid}:{sid}:{tid}")])
        await q.message.reply_text(
            "📝 Kaunsa test delete karna hai?",
            reply_markup=InlineKeyboardMarkup(btns))
        return
    if data.startswith("deltest:"):
        _, cid, sid, tid = data.split(":")
        t = dbm.get_test(cid, sid, tid)
        if not t:
            await q.message.reply_text("❌ Test nahi mila.")
            return
        from keyboards import confirm_delete_keyboard
        context.user_data.pop("astate", None)
        await q.message.reply_text(
            f"⚠️ <b>'{t['title']}'</b> ({len(t.get('questions', []))} Qs) delete kar dun?",
            reply_markup=confirm_delete_keyboard("test", cid, sid, tid), parse_mode="HTML")
        return
    if data.startswith("asub:"):
        cid = data.split(":")[1]
        c = dbm.get_cat(cid)
        if not c:
            await q.message.reply_text("❌ Category nahi mili.")
            return
        st["step"] = "wait_sub_name"
        st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text(f"📁 <b>{c['name']}</b> → sub-category ka naam bhejo:", parse_mode="HTML")
    elif data.startswith("atest:") or data.startswith("atestpdf:"):
        cid = data.split(":")[1]
        c = dbm.get_cat(cid)
        if not c:
            await q.message.reply_text("❌ Category nahi mili.")
            return
        if not c.get("subjects"):
            await q.message.reply_text(
                f"❌ <b>{c['name']}</b> me koi sub-category nahi. Pehle 📁 Sub-category banao.",
                parse_mode="HTML")
            return
        is_pdf = data.startswith("atestpdf:")
        st["step"] = "wait_sub_for_testpdf" if is_pdf else "wait_sub_for_test"
        st["cid"] = cid
        context.user_data["astate"] = st
        await q.message.reply_text(
            f"📂 <b>{c['name']}</b> → sub-category chuno:",
            reply_markup=sub_inline("tsubpdf" if is_pdf else "tsub2", cid),
            parse_mode="HTML")
    elif data.startswith("tsub2:") or data.startswith("tsubpdf:"):
        _, cid, sid = data.split(":")
        c = dbm.get_cat(cid)
        s = dbm.get_sub(cid, sid)
        if not s:
            await q.message.reply_text("❌ Sub-category nahi mili.")
            return
        is_pdf = data.startswith("tsubpdf:")
        if is_pdf:
            st.update({"step": "uploading_test_pdf", "cid": cid, "sid": sid, "count": 0})
            context.user_data["astate"] = st
            n = dbm.next_test_number_in(cid, sid)
            await q.message.reply_text(
                f"✅ <b>{c['name']} › {s['name']}</b> select!\n"
                f"Ab PDF bhejo → <b>Test {n}</b> ban jayega.\n"
                f"Format:\n<code>{Q_FMT}</code>\nKhatam ho to /cancel.",
                parse_mode="HTML")
        else:
            st.update({"step": "wait_test_body_simple", "cid": cid, "sid": sid})
            context.user_data["astate"] = st
            n = dbm.next_test_number_in(cid, sid)
            await q.message.reply_text(
                f"✅ <b>{c['name']} › {s['name']}</b> select!\n"
                f"Ab Q-format text paste karo → <b>Test {n}</b> ban jayega.\n"
                f"<code>{Q_FMT}</code>",
                parse_mode="HTML")


async def handle_pdf(update, context):
    from config import ADMIN_ID
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Permission nahi.")
        return
    st = context.user_data.get("astate", {})
    step = st.get("step")
    if step == "uploading_test_pdf" and st.get("cid") and st.get("sid"):
        await handle_test_pdf(update, context, st)
        return
    # bina flow ke seedha PDF: category/sub chuno, phir test banega
    context.user_data["astate"] = {"step": "pick_cat_for_testpdf"}
    from keyboards import cat_inline
    await update.message.reply_text(
        "📄 PDF mili! Kis <b>category</b> me Test banana hai?",
        reply_markup=cat_inline("atestpdf"), parse_mode="HTML")
    # PDF ko yaad rakho taaki category/sub chunne ke baad use kar sakein
    context.user_data["pending_pdf"] = {
        "file_id": update.message.document.file_id,
        "file_name": update.message.document.file_name or "test.pdf",
    }


async def handle_test_pdf(update, context, st):
    import os
    import tempfile
    s = dbm.get_sub(st["cid"], st["sid"])
    if not s:
        await update.message.reply_text("❌ Sub-category nahi mili.")
        return
    # pending PDF (bina flow bheji) ho to wahi use karo
    pending = context.user_data.pop("pending_pdf", None)
    if pending and not (update.message.document and update.message.document.file_id):
        file_id = pending["file_id"]
        fname = pending["file_name"]
    else:
        file_id = update.message.document.file_id
        fname = update.message.document.file_name or "test.pdf"
    await update.message.reply_text(f"⏳ '{fname}' padh raha hoon...")
    try:
        tg_file = await context.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)
        raw = pdf_to_text(tmp_path)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"pdf download fail: {e}")
        await update.message.reply_text("❌ PDF download fail. Dobara bhejo.")
        return
    qs = parse_questions(raw or "")
    if not qs:
        preview = (raw or "")[:500]
        await update.message.reply_text(f"❌ Valid Q nahi mile.\nMila:\n{preview}")
        return
    n = dbm.next_test_number_in(st["cid"], st["sid"])
    title = f"Test {n}"
    tid = dbm.new_id("t", "test")
    s["tests"][tid] = {"title": title, "questions": qs, "source_pdf": fname}
    st["count"] = st.get("count", 0) + 1
    dbm.save_data()
    c = dbm.get_cat(st["cid"])
    await update.message.reply_text(
        f"✅ <b>{title}</b> → {c['name']} › {s['name']}! {len(qs)} Qs.\n"
        "Aur PDF bhejo ya /cancel.",
        parse_mode="HTML")

