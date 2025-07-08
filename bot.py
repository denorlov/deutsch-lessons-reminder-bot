import asyncio
from datetime import datetime, timedelta
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters, CallbackQueryHandler

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, select, delete, insert

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

scheduler = AsyncIOScheduler()

lessons = [
    {"title" : "Lektion 1. Личные местоимения", "link": "https://web.telegram.org/a/#-1002054418094_43"},
    {"title" : "Lektion 2. Тренировка личных местоимений", "link": "https://web.telegram.org/a/#-1002054418094_52"},
    {"title" : "Lektion 3. Глагол sein (быть)", "link": "https://web.telegram.org/a/#-1002054418094_58"}
]

main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📚 Уроки на сегодня")],
    [KeyboardButton("⚙️ Настроить расписание")]
], resize_keyboard=True)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True)
    schedule = Column(String, default='everyday 08:00')

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    lesson_index = Column(Integer)
    remind_at = Column(DateTime)

def schedule_checker(application):
    # job_id = f"reminder_{user_id}"
    # scheduler.remove_job(job_id=job_id, jobstore=None) if scheduler.get_job(job_id) else None
    # scheduler.add_job(
    #     send_lesson,
    #     'interval',
    #     days=interval_days,
    #     start_date=datetime.now().replace(hour=hour, minute=minute, second=0) + timedelta(days=0),
    #     args=[chat_id, user_id, context],
    #     id=job_id,
    #     replace_existing=True
    # )
    #
    # initialise using all registered users and their schedules
    scheduler.add_job(check_reminders, "interval", days=1, args=[application])
    scheduler.start()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(chat_id=chat_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            reminder = Reminder(user_id=user.id, lesson_index=0, remind_at=datetime.now())
            session.add(reminder)
            await session.commit()

    await show_today_lessons(update, chat_id)

async def show_today_lessons(update: Update, chat_id):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start")
            return

        result = await session.execute(
            select(Reminder.lesson_index).where(
                Reminder.user_id == user.id,
                Reminder.remind_at <= datetime.now()
            )
        )
        indices = sorted(set(row[0] for row in result.fetchall()))

        if not indices:
            await update.message.reply_text("На сегодня нет уроков для напоминания.")
            return

        msg = "📋 Уроки на сегодня:"
        for idx in indices:
            if 0 <= idx < len(lessons):
                lesson = lessons[idx]
                msg += f"<a href='{lesson['link']}'>Урок {lesson['title']}</a>"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text:String = update.message.text.lower()
    chat_id = update.effective_chat.id

    if "уроки" in text and "сегодня" in text:
        await show_today_lessons(update, chat_id)
    elif "уроки" in text and "все" in text:
        show_all_lessons()
    elif text == "⚙️ Настроить расписание":
        await update.message.reply_text("Пока задай вручную: /set_schedule weekdays 08:00 21:00")
    else:
        await update.message.reply_text("Не понимаю. Выбери из меню.")

def build_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я прошел, следующий", callback_data="next_lesson")],
        [InlineKeyboardButton("✅ Повторить предыдущий", callback_data="prev_lesson")],
        [
            InlineKeyboardButton("🔁 Через 1д", callback_data="remind_1"),
            InlineKeyboardButton("🔁 2д", callback_data="remind_2"),
            InlineKeyboardButton("🔁 3д", callback_data="remind_3")
        ]
    ])

# async def send_lesson(chat_id, user_id, context: ContextTypes.DEFAULT_TYPE):
#     idx = user_data.get(user_id, {}).get("lesson_index", 0)
#     if idx < 0: idx = 0
#     if idx >= len(lessons): idx = len(lessons) - 1
#     user_data[user_id]["lesson_index"] = idx
#     lesson = lessons[idx]
#     text = f"📘 Пройди урок номер {lesson['number']}, ссылка: {lesson['link']}"
#     await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_keyboard())

# async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     user_id = query.from_user.id
#     await query.answer()
#
#     if query.data == "next_lesson":
#         user_data[user_id]["lesson_index"] += 1
#         await send_lesson(query.message.chat_id, user_id, context)
#
#     elif query.data == "prev_lesson":
#         user_data[user_id]["lesson_index"] -= 1
#         await send_lesson(query.message.chat_id, user_id, context)
#
#     elif query.data == "remind_later":
#         keyboard = InlineKeyboardMarkup([
#             [InlineKeyboardButton("Через 1 день", callback_data="remind_in_1")],
#             [InlineKeyboardButton("Через 2 дня", callback_data="remind_in_2")],
#             [InlineKeyboardButton("Через 3 дня", callback_data="remind_in_3")]
#         ])
#         await query.edit_message_reply_markup(reply_markup=keyboard)
#
#     elif query.data.startswith("remind_in_"):
#         days = int(query.data.split("_")[-1])
#         schedule_reminder(user_id, query.message.chat_id, interval_days=days, context=context)
#         await context.bot.send_message(chat_id=query.message.chat_id, text=f"📅 Хорошо! Напомню через {days} дней.")
#
# def schedule_reminder(user_id, chat_id, interval_days, context, hour=8, minute=0):
#     job_id = f"reminder_{user_id}"
#     scheduler.remove_job(job_id=job_id, jobstore=None) if scheduler.get_job(job_id) else None
#     scheduler.add_job(
#         send_lesson,
#         'interval',
#         days=interval_days,
#         start_date=datetime.now().replace(hour=hour, minute=minute, second=0) + timedelta(days=0),
#         args=[chat_id, user_id, context],
#         id=job_id,
#         replace_existing=True
#     )

async def send_lesson_by_user(user, reminder, context):
    index = reminder.lesson_index
    if 0 <= index < len(lessons):
        lesson = lessons[index]
        text = f"📘 Пройди урок {lesson['title']} — {lesson['link']}"

        keyboard = build_keyboard()
        await context.bot.send_message(chat_id=user.chat_id, text=text, reply_markup=keyboard)


async def check_reminders(context: CallbackContext):
    now = datetime.now()
    async with async_session() as session:
        result = await session.execute(select(Reminder).join(User).where(Reminder.remind_at <= now))
        reminders = result.scalars().all()
        for reminder in reminders:
            user = await session.get(User, reminder.user_id)
            await send_lesson_by_user(user, reminder, context)
            await session.commit()

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Привет {update.effective_user.first_name}!')

async def show_all_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📚 Все уроки курса:"
    for idx, lesson in enumerate(lessons):
        msg += f"<a href='https://t.me/{context.bot.username}?start=lesson{idx}'>Урок {lesson['title']}</a><br/>"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("all_lessons", show_all_lessons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    schedule_checker(app)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
