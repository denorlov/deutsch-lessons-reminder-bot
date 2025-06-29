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

DATABASE_URL = (
    f"postgresql+asyncpg://{os.environ['PGUSER']}:{os.environ['PGPASSWORD']}"
    f"@{os.environ['PGHOST']}:{os.environ['PGPORT']}/{os.environ['PGDATABASE']}"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

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

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True)
    current_lesson = Column(Integer, default=0)
    schedule = Column(String, default='everyday 08:00')

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    lesson_index = Column(Integer)
    remind_at = Column(DateTime)

def schedule_checker(application):
    scheduler.add_job(send_scheduled_lessons, "interval", minutes=1, args=[application])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[application])
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

    await update.message.reply_text(
        "Привет! Я буду напоминать тебе проходить уроки.",
        reply_markup=main_keyboard
    )

async def send_scheduled_lessons(context: CallbackContext):
    now = datetime.now().strftime("%H:%M")
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        for user in users:
            if user.schedule.startswith("everyday"):
                times = user.schedule.split()[1:]
                if now in times:
                    await send_lesson(user.chat_id, user.id, context)

async def send_lesson(chat_id, user_id, context: CallbackContext):
    async with async_session() as session:
        user = await session.get(User, user_id)
        index = user.current_lesson
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
    async with async_session() as session:
        result = await session.execute(select(Reminder).join(User).where(Reminder.remind_at <= now))
        reminders = result.scalars().all()
        for reminder in reminders:
            user = await session.get(User, reminder.user_id)
            await send_lesson(user.chat_id, user.id, context)
            await session.delete(reminder)
        await session.commit()

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
