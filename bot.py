import asyncio
from datetime import datetime, timedelta
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import os

TOKEN = os.environ.get("TOKEN")
DB_FILE = "lessons.db"

scheduler = AsyncIOScheduler()
lessons = [
    {"number": 1, "link": "https://example.com/lesson1"},
    {"number": 2, "link": "https://example.com/lesson2"},
    {"number": 3, "link": "https://example.com/lesson3"},
]

main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📚 Уроки на сегодня")],
    [KeyboardButton("⚙️ Настроить расписание")]
], resize_keyboard=True)


def schedule_checker(application):
    scheduler.add_job(send_scheduled_lessons, "interval", minutes=1, args=[application])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[application])
    scheduler.start()


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            current_lesson INTEGER DEFAULT 0,
            schedule TEXT DEFAULT 'everyday 08:00'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lesson_index INTEGER,
            remind_at TEXT
        )""")
        await db.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
        await db.execute("""
                    INSERT INTO reminders (user_id, lesson_index, remind_at)
                    SELECT id, 0, ?
                    FROM users
                    WHERE chat_id = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM reminders WHERE user_id = users.id AND lesson_index = 0
                    )
        """, (datetime.now().isoformat(), chat_id))
        await db.commit()
    await update.message.reply_text("Привет! Я буду напоминать тебе проходить уроки.", reply_markup=main_keyboard)

    await db.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))



async def send_scheduled_lessons(context: CallbackContext):
    now = datetime.now().strftime("%H:%M")
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id, chat_id, schedule FROM users") as cursor:
            async for user_id, chat_id, schedule in cursor:
                times = schedule.split()[1:] if schedule.startswith("everyday") else []
                if now in times:
                    await send_lesson(chat_id, user_id, context)


async def send_lesson(chat_id, user_id, context: CallbackContext):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT current_lesson FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            index = row[0] if row else 0
    if 0 <= index < len(lessons):
        lesson = lessons[index]
        text = f"📘 Пройди урок {lesson['number']} — {lesson['link']}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Я прошёл — след. урок", callback_data="next_lesson")],
            [
                InlineKeyboardButton("🔁 Через 1д", callback_data="remind_1"),
                InlineKeyboardButton("🔁 3д", callback_data="remind_3"),
                InlineKeyboardButton("🔁 5д", callback_data="remind_5")
            ]
        ])
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


async def check_reminders(context: CallbackContext):
    now = datetime.now()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT r.id, u.chat_id, u.id, r.lesson_index, r.remind_at FROM reminders r JOIN users u ON u.id = r.user_id") as cursor:
            async for r_id, chat_id, user_id, index, remind_at in cursor:
                if now >= datetime.fromisoformat(remind_at):
                    await send_lesson(chat_id, user_id, context)
                    await db.execute("DELETE FROM reminders WHERE id = ?", (r_id,))
                    await db.commit()


async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer("Stub")))

    schedule_checker(app)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
