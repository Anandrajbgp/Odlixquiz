"""Admin handlers - category, sub-category, PDF se Test (Router)."""
import logging

import database as dbm
from keyboards import admin_home_panel, admin_stats_line
from parser_utils import clean_text

import admin_categories
import admin_tests
import admin_pdf
import admin_live_schedule
import admin_broadcast

logger = logging.getLogger(__name__)


async def open_admin_panel_chat(update, context):
    txt, kb = admin_home_panel(admin_stats_line())
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def admin_panel_callback(update, context, data):
    """Admin panel ke inline buttons."""
    q = update.callback_query
    act = data.split(":", 1)[1] if ":" in data else ""
    if data.startswith(("livecat:", "livesub:", "livetest:", "hidecat:", "qtime:", "qtimechg:", "qtimepick:", "schcat:", "schsub:", "schtest:", "schdel:")):
        st = context.user_data.get("astate", {})
        await admin_callback(update, context, data, st)
        return True

    if act == "del":
        from keyboards import delete_menu
        await q.message.reply_text("🗑 <b>Kya delete karna hai?</b>", reply_markup=delete_menu(), parse_mode="HTML")
    elif act == "delcat":
        await admin_categories.pick_delcat(update, context)
    elif act == "delsub":
        await admin_categories.pick_delsub(update, context)
    elif act == "deltest":
        await admin_tests.pick_deltest(update, context)
    elif act == "addcat":
        await admin_categories.addcat_start(update, context)
    elif act == "addsub":
        await admin_categories.addsub_start(update, context)
    elif act == "addtestpdf":
        await admin_pdf.addtestpdf_start(update, context)
    elif act == "addtest":
        await admin_tests.addtest_start(update, context)
    elif act == "send":
        await admin_broadcast.send_start(update, context)
    elif act == "targets":
        await admin_broadcast.show_targets(update, context)
    elif act == "live":
        await admin_live_schedule.live_menu(update, context)
    elif act == "schedule":
        await admin_live_schedule.schedule_menu(update, context)
    elif act == "schadd":
        await admin_live_schedule.schadd_start(update, context)
    elif act == "schlist":
        await admin_live_schedule.schlist(update, context)
        return True
    elif act == "hidecat":
        await admin_categories.hidecat_start(update, context)
    elif act == "autofwd":
        await admin_broadcast.toggle_autofwd(update, context)
        return True
    elif act == "livestop":
        await admin_live_schedule.livestop(update, context)
        return True
    elif act == "stats":
        await q.message.reply_text(admin_stats_line(), parse_mode="HTML")
    elif act == "scores":
        from keyboards import leaderboard_text
        await q.message.reply_text(leaderboard_text(), parse_mode="HTML")
    elif act == "allhist":
        hist = dbm.db.get("history", {})
        if not hist:
            await q.message.reply_text("Koi attempt nahi.")
            return True
        lines = []
        for uid2, arr in hist.items():
            for e in arr[-3:]:
                lines.append(f"{e.get('name', uid2)} | {e.get('cat','')}/{e.get('sub','')} → {e.get('score')}/{e.get('total')}")
        await q.message.reply_text("Sabki history:\n" + "\n".join(lines[-15:]))
        return True
    return True


async def admin_text_step(update, context):
    st = context.user_data.get("astate")
    if not st:
        return False
    step = st.get("step")
    if step in ("wait_qtime", "wait_qtime_pdf"):
        txt = clean_text((update.message.text or "").strip())
        if txt == "/cancel":
            context.user_data.pop("astate", None)
            from keyboards import admin_home_panel as _ah, admin_stats_line as _as
            t0, k0 = _ah(_as())
            await update.message.reply_text(f"Time 30s default rakha.\n\n{t0}", reply_markup=k0, parse_mode="HTML")
            return True
        return True  # time button se chuno

    txt = clean_text(update.message.text.strip())
    if step == "wait_cat_name":
        return await admin_categories.process_addcat_text(update, context, txt)
    if step == "wait_sub_name":
        return await admin_categories.process_addsub_text(update, context, txt, st)
    if step == "wait_test_body_simple":
        return await admin_tests.process_test_body(update, context, txt, st)
    if step == "wait_schedule_time":
        return await admin_live_schedule.process_schedule_time(update, context, txt, st)
    return False


async def admin_callback(update, context, data, st):
    """Category -> sub-category pick flow + delete flow + delete confirm."""
    if data.startswith("deldo:del:"):
        parts = data.split(":")
        kind = parts[2] if len(parts) > 2 else ""
        cid = parts[3] if len(parts) > 3 else ""
        sid = parts[4] if len(parts) > 4 else ""
        tid = parts[5] if len(parts) > 5 else ""
        if kind == "cat":
            await admin_categories.execute_del_cat(update, context, cid)
        elif kind == "sub":
            await admin_categories.execute_del_sub(update, context, cid, sid)
        elif kind == "test":
            await admin_tests.execute_del_test(update, context, cid, sid, tid)
        else:
            await update.callback_query.message.reply_text("❌ Samajh nahi aaya.")
        return

    if data.startswith("delcat:"):
        cid = data.split(":")[1]
        await admin_categories.confirm_del_cat(update, context, cid)
        return
    if data.startswith("delsubcat:"):
        cid = data.split(":")[1]
        await admin_categories.pick_sub_for_delsub(update, context, cid, st)
        return
    if data.startswith("delsub:"):
        _, cid, sid = data.split(":")
        await admin_categories.confirm_del_sub(update, context, cid, sid)
        return
    if data.startswith("deltestcat:"):
        cid = data.split(":")[1]
        await admin_tests.pick_sub_for_deltest(update, context, cid, st)
        return
    if data.startswith("deltestsub:"):
        _, cid, sid = data.split(":")
        await admin_tests.pick_test_for_del(update, context, cid, sid, st)
        return
    if data.startswith("deltest:"):
        _, cid, sid, tid = data.split(":")
        await admin_tests.confirm_del_test(update, context, cid, sid, tid)
        return

    if data.startswith("hidecat:"):
        cid = data.split(":")[1]
        await admin_categories.toggle_hide_cat(update, context, cid)
        return

    if data.startswith("qtime:"):
        _, cid, sid, tid, sec = data.split(":")
        await admin_tests.qtime_set(update, context, cid, sid, tid, sec)
        return
    if data.startswith("qtimechg:"):
        _, cid, sid, tid, sec = data.split(":")
        await admin_tests.qtime_change(update, context, cid, sid, tid, sec)
        return
    if data.startswith("qtimepick:"):
        _, cid, sid, tid = data.split(":")
        await admin_tests.qtime_pick(update, context, cid, sid, tid)
        return

    if data.startswith("livecat:"):
        cid = data.split(":")[1]
        await admin_live_schedule.pick_sub_for_live(update, context, cid, st)
        return
    if data.startswith("livesub:"):
        _, cid, sid = data.split(":")
        await admin_live_schedule.pick_test_for_live(update, context, cid, sid)
        return
    if data.startswith("livetest:"):
        _, cid, sid, tid = data.split(":")
        await admin_live_schedule.start_live_test(update, context, cid, sid, tid)
        return

    if data.startswith("schcat:"):
        cid = data.split(":")[1]
        await admin_live_schedule.pick_sub_for_sch(update, context, cid, st)
        return
    if data.startswith("schsub:"):
        _, cid, sid = data.split(":")
        await admin_live_schedule.pick_test_for_sch(update, context, cid, sid)
        return
    if data.startswith("schtest:"):
        _, cid, sid, tid = data.split(":")
        await admin_live_schedule.prompt_schedule_time(update, context, cid, sid, tid)
        return
    if data.startswith("schdel:"):
        idx_str = data.split(":")[1]
        await admin_live_schedule.schdel(update, context, idx_str)
        return

    if data.startswith("asub:"):
        cid = data.split(":")[1]
        await admin_categories.pick_sub_for_addsub(update, context, cid, st)
        return
    elif data.startswith("atest:"):
        cid = data.split(":")[1]
        await admin_tests.pick_sub_for_test(update, context, cid, st)
        return
    elif data.startswith("atestpdf:"):
        cid = data.split(":")[1]
        await admin_pdf.pick_sub_for_testpdf(update, context, cid, st)
        return
    elif data.startswith("tsub2:"):
        _, cid, sid = data.split(":")
        await admin_tests.prompt_test_body(update, context, cid, sid, st)
        return
    elif data.startswith("tsubpdf:"):
        _, cid, sid = data.split(":")
        await admin_pdf.prompt_test_pdf(update, context, cid, sid, st)
        return

async def handle_pdf(update, context):
    await admin_pdf.handle_pdf_file(update, context)
