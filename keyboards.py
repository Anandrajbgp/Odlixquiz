"""Reply + Inline keyboards.

User: chat ke andar inline panel (edit-based navigation).
Admin: full control panel.
"""
from telegram import (
    BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
)

import database as dbm
from config import ADMIN_ID, PAGE_SIZE


# ---------- shared UI helpers ----------
def nav_row(home_cb="home:main", back_cb=None):
    row = []
    if back_cb:
        row.append(InlineKeyboardButton("⬅ Back", callback_data=back_cb))
    row.append(InlineKeyboardButton("🏠 Home", callback_data=home_cb))
    return row


def breadcrumb(cat=None, sub=None, test=None):
    parts = ["🏠"]
    if cat:
        parts.append(cat[:30])
    if sub:
        parts.append(sub[:30])
    if test:
        parts.append(test[:30])
    return " › ".join(parts)


async def edit_or_send(query, text, reply_markup=None, parse_mode="HTML"):
    """Purana panel hi update karo (chat saaf rahe). Fail ho to naya bhejo."""
    try:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception:
        try:
            await query.message.reply_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            return False
        except Exception:
            return False


# ---------- USER: home panel (Category -> Sub-category -> Test) ----------
def user_home_panel(uid=None):
    """User home panel — Categories → Tests."""
    rows = [
        [InlineKeyboardButton("📂 Browse Categories", callback_data="home:cats")],
        [InlineKeyboardButton("📜 History", callback_data="home:history"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="home:board")],
    ]
    if uid is not None:
        from quiz import _paused_quizzes
        if uid in _paused_quizzes:
            rows.insert(0, [InlineKeyboardButton("▶️ Resume Quiz", callback_data="quiz:resume")])
    return InlineKeyboardMarkup(rows)


def stop_quiz_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏹ Stop Quiz", callback_data="quiz:stop")],
    ])


def leaderboard_text():
    from config import LEADERBOARD_LIMIT
    rows = dbm.get_leaderboard(LEADERBOARD_LIMIT)
    if not rows:
        return "🏆 No scores yet — take a test first!"
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        pct = round(r["best"] * 100 / max(r["total"], 1))
        lines.append(f"{medal} {r['name']} — {r['best']}/{r['total']} ({pct}%)")
    return "🏆 <b>Leaderboard (Best Score):</b>\n" + "\n".join(lines)


def result_keyboard(cid, sid, tid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Review Answers", callback_data=f"rev:0:{cid}:{sid}:{tid}")],
        [InlineKeyboardButton("🔁 Retry Test", callback_data=f"start:{cid}:{sid}:{tid}")],
        [InlineKeyboardButton("📝 Aur Tests", callback_data=f"tsub:{cid}:{sid}"),
         InlineKeyboardButton("🏠 Home", callback_data="home:main")],
    ])


def review_text(detail, idx, total_count):
    from parser_utils import clean_text
    letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    q = clean_text(detail.get("question", ""))[:280]
    opts = detail.get("options", []) or []
    correct = detail.get("correct", 0)
    picked = detail.get("picked", -1)
    lines = [f"🔍 <b>Q{idx + 1}/{total_count}</b>: {q}", ""]
    for i, o in enumerate(opts[:10]):
        mark = ""
        if i == correct:
            mark = " ✅"
        elif i == picked:
            mark = " ❌ (your answer)"
        lines.append(f"{letters[i] if i < len(letters) else i + 1}. {clean_text(str(o))[:90]}{mark}")
    if detail.get("timeout") or picked == -1:
        lines.append("\n⏰ <i>No answer given (timeout).</i>")
    exp = clean_text(detail.get("explanation", ""))
    if exp:
        lines.append(f"\n💡 <i>{exp[:180]}</i>")
    return "\n".join(lines)


def review_keyboard(idx, total_count, cid, sid, tid):
    row = []
    if idx > 0:
        row.append(InlineKeyboardButton("◀ Prev", callback_data=f"rev:{idx - 1}:{cid}:{sid}:{tid}"))
    if idx < total_count - 1:
        row.append(InlineKeyboardButton("Next ▶", callback_data=f"rev:{idx + 1}:{cid}:{sid}:{tid}"))
    kb = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🔁 Retry", callback_data=f"start:{cid}:{sid}:{tid}"),
               InlineKeyboardButton("🏠 Home", callback_data="home:main")])
    return InlineKeyboardMarkup(kb)


# ---------- ADMIN: category + sub-category + test ----------
def admin_home_panel(stats_line=""):
    txt = "⚙️ ADMIN PANEL"
    if stats_line:
        txt += f"\n{stats_line}"
    txt += ("\n\nFirst create a <b>Category</b>, then add <b>Sub-categories</b>, "
            "then send <b>PDF → Tests are created automatically</b>.\n"
            "Choose an option below:")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Category banao", callback_data="adm:addcat"),
         InlineKeyboardButton("📁 Sub-category", callback_data="adm:addsub")],
        [InlineKeyboardButton("📄 PDF se Test", callback_data="adm:addtestpdf"),
         InlineKeyboardButton("📝 Text se Test", callback_data="adm:addtest")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm:send"),
         InlineKeyboardButton("📡 Targets", callback_data="adm:targets")],
        [InlineKeyboardButton("🔴 LIVE Test", callback_data="adm:live"),
         InlineKeyboardButton("👁 Hide/Show Cat", callback_data="adm:hidecat")],
        [InlineKeyboardButton("🗑 Delete", callback_data="adm:del"),
         InlineKeyboardButton("📊 Stats", callback_data="adm:stats")],
        [InlineKeyboardButton("🏆 Scores", callback_data="adm:scores"),
         InlineKeyboardButton("📜 History (sab)", callback_data="adm:allhist")],
    ])
    return txt, kb


def delete_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Category delete", callback_data="adm:delcat")],
        [InlineKeyboardButton("📁 Sub-category delete", callback_data="adm:delsub")],
        [InlineKeyboardButton("📝 Test delete", callback_data="adm:deltest")],
    ])


def confirm_delete_keyboard(kind, cid, sid="", tid=""):
    cb = f"del:{kind}:{cid}:{sid}:{tid}"
    no = "delmenu"
    if kind == "sub":
        no = f"delback:delsub:{cid}"
    elif kind == "test":
        no = f"delback:deltest:{cid}:{sid}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"deldo:{cb}")],
        [InlineKeyboardButton("❌ No", callback_data=no)],
    ])


def admin_stats_line():
    nc = len(dbm.db["categories"])
    ns = sum(len(c["subjects"]) for c in dbm.db["categories"].values())
    nt = sum(len(s["tests"]) for c in dbm.db["categories"].values() for s in c["subjects"].values())
    nq = sum(len(t["questions"]) for c in dbm.db["categories"].values()
             for s in c["subjects"].values() for t in s["tests"].values())
    npdf = sum(len(s["pdfs"]) for c in dbm.db["categories"].values() for s in c["subjects"].values())
    nh = sum(len(v) for v in (dbm.db.get("history", {}) or {}).values())
    return f"📦 Cat:{nc} Sub:{ns} Tests:{nt} Qs:{nq} PDFs:{npdf} Attempts:{nh}"


def admin_quick_menu():
    """Admin ke liye bhi koi neeche keyboard nahi - sab chat ke andar."""
    from telegram import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


def user_menu():
    return None


def admin_menu():
    from telegram import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


def menu_for(uid):
    return admin_quick_menu() if uid == ADMIN_ID else None


# ---------- Telegram ☰ Menu Button (chat-box ke paas) ----------
USER_COMMANDS = [
    BotCommand("start", "🏠 Home — Category / Test / History"),
    BotCommand("home", "🏠 Home panel"),
    BotCommand("test", "📂 Choose Category"),
    BotCommand("history", "📜 My History"),
    BotCommand("leaderboard", "🏆 Top Scores"),
    BotCommand("cancel", "❌ Cancel"),
]

ADMIN_COMMANDS = [
    BotCommand("start", "🏠 Home"),
    BotCommand("home", "🏠 Home panel"),
    BotCommand("admin", "⚙️ Admin Panel"),
    BotCommand("test", "📝 Take Test"),
    BotCommand("history", "📜 History"),
    BotCommand("leaderboard", "🏆 Leaderboard"),
    BotCommand("live", "🔴 LIVE test bhejo (30-sec gap)"),
    BotCommand("livestop", "⏹ LIVE roko"),
    BotCommand("broadcast", "📢 Text bhejo"),
    BotCommand("send", "📢 Jo bhejoge sabko jayega"),
    BotCommand("targets", "📡 Linked groups"),
    BotCommand("cancel", "❌ Cancel"),
]


async def setup_menu_button(app):
    """User scope + Admin scope me alag ☰ menu lagao."""
    try:
        from telegram import BotCommandScopeChat, BotCommandScopeDefault
        await app.bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
        if ADMIN_ID:
            await app.bot.set_my_commands(
                ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"menu button setup fail: {e}")


# Test ke har Q par kitna time (sec) - LIVE + personal dono isi se chalenge
QTIME_OPTIONS = [10, 20, 30, 60, 120]
DEFAULT_QTIME = 30


def fmt_qtime(sec) -> str:
    try:
        sec = int(sec or DEFAULT_QTIME)
    except Exception:
        sec = DEFAULT_QTIME
    if sec >= 60:
        m = sec // 60
        return f"{m} min" if sec % 60 == 0 else f"{m}m {sec % 60}s"
    return f"{sec}s"


def qtime_keyboard(prefix, cid, sid, tid):
    btns = []
    row = []
    for sec in QTIME_OPTIONS:
        row.append(InlineKeyboardButton(
            f"⏱ {fmt_qtime(sec)}", callback_data=f"{prefix}:{cid}:{sid}:{tid}:{sec}"))
        if len(row) == 3:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    return InlineKeyboardMarkup(btns)


def set_test_qtime(cid, sid, tid, sec: int):
    t = dbm.get_test(cid, sid, tid)
    if not t:
        return False
    try:
        sec = max(5, min(int(sec), 600))
    except Exception:
        sec = DEFAULT_QTIME
    t["qtime"] = sec
    dbm.save_data()
    return True


def get_test_qtime(cid=None, sid=None, tid=None, t=None) -> int:
    try:
        if t is None and cid and sid and tid:
            t = dbm.get_test(cid, sid, tid)
        if isinstance(t, dict) and t.get("qtime"):
            return max(5, min(int(t["qtime"]), 600))
    except Exception:
        pass
    return DEFAULT_QTIME


def cat_inline(prefix, page=0, include_hidden=None):
    items = list(dbm.db["categories"].items())
    # LIVE/hidden category user ko kabhi mat dikhao; admin ko sab dikhao
    if include_hidden is None:
        admin_prefixes = ("a", "del", "live", "hide")
        include_hidden = str(prefix).startswith(admin_prefixes)
    if not include_hidden:
        items = [(cid, c) for cid, c in items if not c.get("hidden")]
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    btns = []
    for cid, c in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        nsub = len(c.get("subjects", {}))
        ntest = sum(len(s.get("tests", {})) for s in c.get("subjects", {}).values())
        npdf = sum(len(s.get("pdfs", [])) for s in c.get("subjects", {}).values())
        hide_tag = " 🔒LIVE" if c.get("hidden") else ""
        btns.append([InlineKeyboardButton(
            f"📂 {c['name']}{hide_tag} ({ntest} Test, {nsub} Sub)",
            callback_data=f"{prefix}:{cid}")])
    if not btns:
        btns = [[InlineKeyboardButton("Empty", callback_data="noop")]]
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"page:{prefix}:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶", callback_data=f"page:{prefix}:{page + 1}"))
    if nav:
        btns.append(nav)
    return InlineKeyboardMarkup(btns)


def sub_inline(prefix, cid):
    c = dbm.get_cat(cid)
    if not c:
        return None
    btns = []
    for sid, s in c.get("subjects", {}).items():
        btns.append([InlineKeyboardButton(
            f"📁 {s['name']} ({len(s.get('tests', {}))} Test)",
            callback_data=f"{prefix}:{cid}:{sid}")])
    btns.append(nav_row(back_cb=f"back:{prefix}"))
    return InlineKeyboardMarkup(btns)


def test_inline(cid, sid):
    s = dbm.get_sub(cid, sid)
    if not s:
        return None
    import re
    def sortkey(item):
        tid, t = item
        m = re.search(r"(\d+)", t.get("title", "") or "")
        return (int(m.group(1)) if m else 9999, t.get("title", ""))
    tests = sorted((s.get("tests", {}) or {}).items(), key=sortkey)
    btns = []
    for tid, t in tests:
        btns.append([InlineKeyboardButton(
            f"📝 {t.get('title', tid)} ({len(t.get('questions', []))} Qs)",
            callback_data=f"start:{cid}:{sid}:{tid}")])
    if not btns:
        btns = [[InlineKeyboardButton("Koi test nahi - admin jald add karega",
                                      callback_data="noop")]]
    btns.append(nav_row(back_cb=f"bsub:{cid}"))
    return InlineKeyboardMarkup(btns)


def pdf_list_inline(cid, sid, back_cb=None):
    s = dbm.get_sub(cid, sid)
    if not s:
        return None
    btns = []
    for i, p in enumerate(s.get("pdfs", []) or []):
        fname = (p.get("file_name") or f"PDF {i + 1}")[:50]
        btns.append([InlineKeyboardButton(
            f"📄 {fname}", callback_data=f"pdf:{cid}:{sid}:{i}")])
    if not btns:
        btns = [[InlineKeyboardButton("Koi PDF nahi", callback_data="noop")]]
    if back_cb:
        btns.append(nav_row(back_cb=back_cb))
    else:
        btns.append(nav_row(back_cb=f"tsub:{cid}:{sid}"))
    return InlineKeyboardMarkup(btns)
