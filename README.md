# OdlixQuiz - Telegram Quiz Bot

Category → Subject → Test/PDF wala Telegram bot.

## Structure

```
bot.py             # shortcut (main.py ko chalata hai), `python bot.py`
main.py            # entry point - handlers register + polling
config.py          # BOT_TOKEN, ADMIN_ID (.env se), paths, constants
database.py        # data.json load/save, categories/subjects/tests/history
keyboards.py       # reply + inline keyboards
parser_utils.py    # Q-format parse + PDF text extract
quiz.py            # poll quiz engine (send, answer, score, history)
handlers_user.py   # /start, Test Do, PDFs, History, callbacks
handlers_admin.py  # Add Category/Subject/Test, PDF upload (study + test-PDF)
```

## Chalana

```powershell
pip install -r requirements.txt
python bot.py        # ya: python main.py
```

## Admin flow

1. `➕ Add Category` → naam (RRB/SSC/12th)
2. `📁 Add Subject` → category → naam (GK/Science)
3. Test: `📝 Add Test` (text paste) ya `📄 PDF se Test` (Q-format PDF)
4. Study PDF: `📤 Upload PDFs` → category → subject → bulk PDFs
5. `📊 Stats` → counts

## Q-format

```
Q: Sawal? | A | B | C | D | Ans: B | Exp: samjhaye
```

Har line 1 question. Sample: `sample_test_format.txt`, `sample_questions.pdf`.
