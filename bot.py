import logging
import aiosqlite
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = "YOUR_BOT_TOKEN"
DB_FILE = "lessons.db"

logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()
scheduler.start()

lessons = [
    {"number": 1, "link": "https://example.com/lesson1"},
    {"number": 2, "link": "https://example.com/lesson2"},
    {"number": 3, "link": "https://example.com/lesson3"},
]

main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📚 Уроки на сегодня")],
    [KeyboardButton("⚙️ Настроить расписание")]
], resize_keyboard=True)


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
        await db.commit()
    await update.message.reply_text("Привет! Я буду напоминать тебе проходить уроки.", reply_markup=main_keyboard)


def build_lesson_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я прошёл — следующий урок", callback_data="next_lesson")],
        [
            InlineKeyboardButton("🔁 Напомнить через 1 день", callback_data="remind_1"),
            InlineKeyboardButton("🔁 Через 3 дня", callback_data="remind_3"),
            InlineKeyboardButton("🔁 Через 5 дней", callback_data="remind_5")
        ]
    ])


async def send_lesson(chat_id, user_id, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT current_lesson FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            index = row[0] if row else 0
        if 0 <= index < len(lessons):
            lesson = lessons[index]
            text = f"📘 Пройди урок номер {lesson['number']}, ссылка: {lesson['link']}"
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_lesson_keyboard())
        else:
            await context.bot.send_message(chat_id=chat_id, text="🎉 Ты прошёл все доступные уроки!")


async def send_specific_lesson(chat_id, user_id, lesson_index, context):
    if 0 <= lesson_index < len(lessons):
        lesson = lessons[lesson_index]
        text = f"🔔 Напоминание!\n📘 Пройди урок номер {lesson['number']}, ссылка: {lesson['link']}"
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_lesson_keyboard())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "📚 Уроки на сегодня":
        await notify_today_lessons(chat_id, context)
    elif text == "⚙️ Настроить расписание":
        await update.message.reply_text("Пока задай вручную: /set_schedule weekdays 08:00 21:00")
    else:
        await update.message.reply_text("Не понимаю. Выбери из меню.")


async def notify_today_lessons(chat_id, context):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return
            user_id = row[0]
    await send_lesson(chat_id, user_id, context)


async def set_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Формат: /set_schedule weekdays 08:00 21:00 или /set_schedule everyday 08:00")
        return

    schedule = " ".join(args)
    chat_id = update.effective_chat.id
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET schedule = ? WHERE chat_id = ?", (schedule, chat_id))
        await db.commit()

    await update.message.reply_text(f"✅ Расписание установлено: {schedule}")


async def send_scheduled_lessons(context: CallbackContext):
    now = datetime.now()
    weekday = now.strftime("%A").lower()

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id, chat_id, schedule FROM users") as cursor:
            async for user_id, chat_id, schedule in cursor:
                parts = schedule.split()
                if parts[0] == "everyday":
                    times = parts[1:]
                elif parts[0] == "weekdays" and weekday in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                    times = parts[1:]
                else:
                    continue

                for t in times:
                    target_time = datetime.strptime(t, "%H:%M").time()
                    if now.hour == target_time.hour and now.minute == target_time.minute:
                        await send_lesson(chat_id, user_id, context)


async def check_reminders(context: CallbackContext):
    now = datetime.now()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("""
            SELECT r.id, u.chat_id, u.id, r.lesson_index 
            FROM reminders r 
            JOIN users u ON u.id = r.user_id
        """) as cursor:
            rows = await cursor.fetchall()

        for reminder_id, chat_id, user_id, lesson_index in rows:
            async with db.execute("SELECT remind_at FROM reminders WHERE id = ?", (reminder_id,)) as cur:
                r = await cur.fetchone()
                remind_time = datetime.fromisoformat(r[0])
                if now >= remind_time:
                    await send_specific_lesson(chat_id, user_id, lesson_index, context)
                    await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
                    await db.commit()


async def my_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await update.message.reply_text("Ты ещё не зарегистрирован, нажми /start")
                return
            user_id = row[0]

        async with db.execute(
                "SELECT lesson_index, remind_at FROM reminders WHERE user_id = ? ORDER BY remind_at", (user_id,)
        ) as cursor:
            reminders = await cursor.fetchall()

    if not reminders:
        await update.message.reply_text("У тебя нет активных напоминаний.")
        return

    text = "📅 Твои активные напоминания:\n"
    for lesson_index, remind_at in reminders:
        if 0 <= lesson_index < len(lessons):
            lesson_num = lessons[lesson_index]['number']
            dt = datetime.fromisoformat(remind_at).strftime("%Y-%m-%d %H:%M")
            text += f"• Урок {lesson_num} — напомнить {dt}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    async with aiosqlite.connect(DB_FILE) as db:
        # Получаем user_id и current урок
        async with db.execute("SELECT id, current_lesson FROM users WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return
            user_id, current = row

        if query.data == "next_lesson":
            if current + 1 < len(lessons):
                await db.execute("UPDATE users SET current_lesson = current_lesson + 1 WHERE id = ?", (user_id,))
                await db.execute("DELETE FROM reminders WHERE user_id = ? AND lesson_index = ?", (user_id, current))
                await db.commit()
                await send_lesson(chat_id, user_id, context)
            else:
                await query.message.reply_text("🎉 Ты уже прошёл все уроки!")

        elif query.data.startswith("remind_"):
            days = int(query.data.split("_")[1])
            remind_at = datetime.now() + timedelta(days=days)

            # Проверяем текущий урок
            async with db.execute("SELECT current_lesson FROM users WHERE id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                current_lesson = row[0] if row else 0

            # Проверяем, есть ли уже напоминание на этот урок
            async with db.execute(
                    "SELECT 1 FROM reminders WHERE user_id = ? AND lesson_index = ?",
                    (user_id, current_lesson)
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await query.message.reply_text("❗ Ты уже установил напоминание на этот урок.")
            else:
                await db.execute(
                    "INSERT INTO reminders (user_id, lesson_index, remind_at) VALUES (?, ?, ?)",
                    (user_id, current_lesson, remind_at.isoformat())
                )
                await db.commit()
                await query.message.reply_text(f"🔔 Окей, напомню через {days} дн(я/дня).")


def schedule_checker(application):
    scheduler.add_job(send_scheduled_lessons, "interval", minutes=1, args=[application])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[application])


if __name__ == "__main__":
    import asyncio
    from telegram.ext import Application

    async def main():
        await init_db()
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("set_schedule", set_schedule))
        app.add_handler(CommandHandler("my_reminders", my_reminders))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(button_handler))

        schedule_checker(app)

        await app.run_polling()

    asyncio.run(main())
