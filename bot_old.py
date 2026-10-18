import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    PollHandler
)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONFIGURATION ---
BOT_TOKEN = "8717079931:AAF9bun6qeS3bExq1dRgec1-pGvWI-tRmgE"          # Apna Telegram Bot Token yahan dalein
ADMIN_ID = 7863379790                  # Apni asli Telegram User ID (Numeric) yahan dalein

# Mock Database for stored PDFs (In real-world, use a database or file system)
stored_pdfs = []

# --- KEYBOARDS ---
def get_user_keyboard():
    keyboard = [[KeyboardButton("📊 Take Trading Test"), KeyboardButton("📚 View PDFs")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("📊 Take Trading Test"), KeyboardButton("📚 View PDFs")],
        [KeyboardButton("⚙️ Admin: View Total Uploads"), KeyboardButton("📤 Admin: Instructions")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- HANDLERS ---

async def start_or_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jab user/admin kuch bhi type karega toh menu dikhayega"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            f"Hello Admin {first_name}! Welcome to your control panel.",
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text(
            f"Hello {first_name}! Welcome to the Trading Test Bot. Select an option:",
            reply_markup=get_user_keyboard()
        )

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buttons ke clicks ko handle karne ke liye"""
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📊 Take Trading Test":
        # Options wala Poll (Quiz) send karna
        questions = ["Bullish Engulfing", "Bearish Engulfing", "Doji", "Hammer"]
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question="Neeche diye gaye patterns mein se kaun sa Trend Reversal pattern hai?",
            options=questions,
            type='quiz',
            correct_option_id=0, # Bullish Engulfing is correct here just for example
            explanation="Bullish Engulfing ek strong bullish trend reversal pattern hai.",
            is_anonymous=False
        )
        
    elif text == "📚 View PDFs":
        if not stored_pdfs:
            await update.message.reply_text("Abhi tak koi PDF upload nahi ki gayi hai.")
        else:
            await update.message.reply_text("Ye rahe aapke educational PDFs:")
            for pdf_id in stored_pdfs:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=pdf_id)

    # Admin specific buttons
    elif text == "⚙️ Admin: View Total Uploads" and user_id == ADMIN_ID:
        await update.message.reply_text(f"Total uploaded PDFs: {len(stored_pdfs)}")
        
    elif text == "📤 Admin: Instructions" and user_id == ADMIN_ID:
        await update.message.reply_text("Admin, aap is chat mein direct koi bhi .pdf file attach karke bhejiye, bot use save kar lega.")
        
    else:
        # Agar koi random text bhejta hai toh wapas menu dikhao
        await start_or_menu(update, context)

async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sirf admin se mili hui PDF ko save karne ke liye"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        # Telegram unique file_id generate karta hai jisse directly send kiya ja sakta hai
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        
        stored_pdfs.append(file_id)
        await update.message.reply_text(f"✅ Success! Document '{file_name}' save ho gaya hai aur ab users ise dekh sakte hain.")
    else:
        await update.message.reply_text("⛔ Aapke paas PDF upload karne ki permission nahi hai.")

def main() -> None:
    """Bot start karne ka main function"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands & Messages handles
    application.add_handler(CommandHandler("start", start_or_menu))
    
    # Handle PDF/Document uploads (Sirf documents ke liye)
    application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    
    # Handle normal text (Buttons aur kuch bhi random bhejne par)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))

    # Run the bot
    print("Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
