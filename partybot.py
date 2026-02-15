from config import TOKEN, ADMIN_ID
import sqlite3
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)

# TOKEN = ("TOKEN")
# ADMIN_ID = ("ADMIN_ID")
SECRET_CODE = "to the end of darkness"
CARD_NUMBER = "6037998291886488"
AMOUNT = "دو میلیون تومان برای هر نفر یا سه میلیون تومان برای زوج"

if not TOKEN or not ADMIN_ID:
    raise ValueError("TOKEN or ADMIN_ID is not set in environment variables!")


ASK_CODE, ASK_NAME, ASK_PAYMENT_ID, ASK_SCREENSHOT = range(4)

# DB
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    payment_id TEXT,
    screenshot_file_id TEXT,
    status TEXT
)
""")
conn.commit()

logging.basicConfig(level=logging.INFO)

# main / start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام لطفا کد را وارد کنید:")
    return ASK_CODE

async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == SECRET_CODE:
        await update.message.reply_text("کد صحیح است.\nنام و نام خانوادگی را وارد کنید:")
        return ASK_NAME
    else:
        await update.message.reply_text("کد اشتباه  ❌")
        return ASK_CODE

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    name = update.message.text

    cursor.execute("INSERT OR REPLACE INTO users (user_id, name, status) VALUES (?, ?, ?)",
                   (user_id, name, "pending"))
    conn.commit()

    await update.message.reply_text(
        f"لطفاً مبلغ {AMOUNT} را به شماره کارت زیر واریز کنید:\n\n{CARD_NUMBER}\n\n"
        "بعد از پرداخت، منتظرم که شناسه پرداخت را ارسال کنید:"
    )
    return ASK_PAYMENT_ID

async def save_payment_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    payment_id = update.message.text

    cursor.execute("UPDATE users SET payment_id=? WHERE user_id=?",
                   (payment_id, user_id))
    conn.commit()

    await update.message.reply_text("حالا اسکرین‌شات پرداخت را ارسال کنید بعد منتظر تأیید باشید در مرحله بعد برای شما لوکیشن را ارسال می‌کنم:")
    return ASK_SCREENSHOT

async def save_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1].file_id

    cursor.execute("UPDATE users SET screenshot_file_id=? WHERE user_id=?",
                   (photo, user_id))
    conn.commit()

    keyboard = [
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")
        ]
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"پرداخت جدید\nUser ID: {user_id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("درخواست شما ثبت شد. منتظر تایید ادمین باشید.")
    return ConversationHandler.END

async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "پرداخت شما تایید شد ✅")
    else:
        cursor.execute("UPDATE users SET status='rejected' WHERE user_id=?", (user_id,))
        conn.commit()
        await context.bot.send_message(user_id, "پرداخت شما رد شد ❌")

async def send_location_to_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT user_id FROM users WHERE status='approved'")
    users = cursor.fetchall()

    for user in users:
        await context.bot.send_location(
            chat_id=user[0],
            latitude=35.6892,
            longitude=51.3890
        )

    await update.message.reply_text("لوکیشن برای همه ارسال شد.")

app = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_code)],
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_name)],
        ASK_PAYMENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_payment_id)],
        ASK_SCREENSHOT: [MessageHandler(filters.PHOTO, save_screenshot)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(handle_admin))
app.add_handler(CommandHandler("sendlocation", send_location_to_paid))

app.run_polling()
