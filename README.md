# OdlixQuiz - Telegram Quiz Bot (Group Edition)

Category → Subject → Test/PDF wala Telegram bot with Telegram Group integration & Auto-Lock discussion.

## Structure

```
bot.py             # shortcut (main.py ko chalata hai), `python bot.py`
main.py            # entry point - handlers register + polling
config.py          # BOT_TOKEN, ADMIN_ID (.env se), paths, constants
database.py        # data.json load/save, categories/subjects/tests/history (with auto-backup recovery)
keyboards.py       # reply + inline keyboards
parser_utils.py    # Robust Q-format parse + PDF text extract
quiz.py            # poll quiz engine + group chat 10-min auto-lock discussion
handlers_user.py   # /start (with start=test deep-link), Test Do, PDFs, History
handlers_admin.py  # Add Category/Subject/Test, PDF upload
```

## Group & Pinned Message Flow

1. **Telegram Group me Pinned Message:** Group ke pinned message me ek Inline Button lagayein:
   `https://t.me/AapkeBotKaUsername?start=test`
2. **Private Chat Menu:** Jaise hi user us button par click karega, bot unke **private chat** me turant Test/Category Menu khol dega.
3. **Auto-Lock Discussion:** Test khatam hone ke baad group chat 10 minutes ke liye open hoti hai aur phir automatic lock (read-only) ho jati hai.

## Chalana

```powershell
pip install -r requirements.txt
python bot.py        # ya: python main.py
```
