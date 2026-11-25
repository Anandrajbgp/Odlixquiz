import logging
import database as dbm
from keyboards import cat_inline, sub_inline, qtime_keyboard
from parser_utils import Q_FMT, parse_questions, pdf_to_text

logger = logging.getLogger(__name__)

async def addtestpdf_start(update, context):
    q = update.callback_query
    context.user_data["astate"] = {"step": "pick_cat_for_testpdf"}
    await q.message.reply_text("📄 Kis category me Test banana hai?", reply_markup=cat_inline("atestpdf"))

async def pick_sub_for_testpdf(update, context, cid, st):
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
    st["step"] = "wait_sub_for_testpdf"
    st["cid"] = cid
    context.user_data["astate"] = st
    await q.message.reply_text(
        f"📂 <b>{c['name']}</b> → sub-category chuno:",
        reply_markup=sub_inline("tsubpdf", cid),
        parse_mode="HTML")

async def prompt_test_pdf(update, context, cid, sid, st):
    q = update.callback_query
    c = dbm.get_cat(cid)
    s = dbm.get_sub(cid, sid)
    if not s:
        await q.message.reply_text("❌ Sub-category nahi mili.")
        return
    st.update({"step": "uploading_test_pdf", "cid": cid, "sid": sid, "count": 0})
    context.user_data["astate"] = st
    n = dbm.next_test_number_in(cid, sid)
    await q.message.reply_text(
        f"✅ <b>{c['name']} › {s['name']}</b> select!\n"
        f"Ab PDF bhejo → <b>Test {n}</b> ban jayega.\n"
        f"Format:\n<code>{Q_FMT}</code>\nKhatam ho to /cancel.",
        parse_mode="HTML")

async def handle_pdf_file(update, context):
    from config import ADMIN_ID
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Permission nahi.")
        return
    st = context.user_data.get("astate", {})
    step = st.get("step")
    if step == "uploading_test_pdf" and st.get("cid") and st.get("sid"):
        await process_test_pdf(update, context, st)
        return

    context.user_data["astate"] = {"step": "pick_cat_for_testpdf"}
    await update.message.reply_text(
        "📄 PDF mili! Kis <b>category</b> me Test banana hai?",
        reply_markup=cat_inline("atestpdf"), parse_mode="HTML")

    context.user_data["pending_pdf"] = {
        "file_id": update.message.document.file_id,
        "file_name": update.message.document.file_name or "test.pdf",
    }

async def process_test_pdf(update, context, st):
    import os
    import tempfile
    s = dbm.get_sub(st["cid"], st["sid"])
    if not s:
        await update.message.reply_text("❌ Sub-category nahi mili.")
        return

    pending = context.user_data.pop("pending_pdf", None)
    if pending and not (update.message.document and getattr(update.message.document, 'file_id', None)):
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
    s["tests"][tid] = {"title": title, "questions": qs, "source_pdf": fname, "qtime": 30}
    st["count"] = st.get("count", 0) + 1
    dbm.save_data()
    c = dbm.get_cat(st["cid"])
    await update.message.reply_text(
        f"✅ <b>{title}</b> → {c['name']} › {s['name']}! {len(qs)} Qs.\n\n"
        f"⏱ <b>Har Q par kitna time?</b> (LIVE channel + personal dono me yahi lagega)\n"
        f"Neeche dabao ya aur PDF bhejo (30s default):",
        reply_markup=qtime_keyboard("qtime", st["cid"], st["sid"], tid),
        parse_mode="HTML")
    context.user_data["astate"] = {"step": "wait_qtime_pdf", "cid": st["cid"], "sid": st["sid"], "tid": tid, "count": st.get("count", 0)}
