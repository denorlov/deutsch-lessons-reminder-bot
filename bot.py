import asyncio
from datetime import datetime, timedelta
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, \
    LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters, \
    CallbackQueryHandler

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, select, delete, insert

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

scheduler = AsyncIOScheduler()

lessons = [
    {"title": "Lektion 1. Личные местоимения", "link": "https://t.me/c/2054418094/48?thread=43"},
    {"title": "Lektion 2. Тренировка личных местоимений", "link": "https://t.me/c/2054418094/56?thread=52"},
    {"title": "Lektion 3. Глагол sein (быть)", "link": "https://t.me/c/2054418094/64?thread=58"}
]

main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📋 Уроки на сегодня")],
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

    await hello(update, context)
    await show_today_lessons(update, context)


async def show_today_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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
        logger.info(f"result: {result}")
        indices = sorted(set(row[0] for row in result.fetchall()))
        logger.info(f"indices: {indices}")

        if not indices:
            await update.message.reply_text("На сегодня нет уроков для напоминания.")
            return

        await update.message.reply_text("📋 Уроки на сегодня:")
        for idx in indices:
            if 0 <= idx < len(lessons):
                lesson = lessons[idx]
                await show_lesson(update, lesson)


async def show_lesson(update, lesson):
    msg = f"<a href='{lesson['link']}'>{lesson['title']}</a>"
    keyboard = build_keyboard()
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                    link_preview_options=LinkPreviewOptions(is_disabled=True))


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start")
            return

        await update.message.reply_text("Пока редактирование не доступно")
        await update.message.reply_text(
            f"Текущее расписание: для user.id={user.id}, chat_id:{user.chat_id}, schedule: {user.schedule}")
        for job in scheduler.get_jobs():
            await update.message.reply_text(
                f"{job.id}, {job.name}, trigger:{job.trigger}, next run time:{job.next_run_time}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"update:{update}, context: {context}")

    text: String = update.message.text.lower()

    if "уроки" in text and "сегодня" in text:
        await show_today_lessons(update, context)
    elif "уроки" in text and "все" in text:
        await show_all_lessons(update, context)
    elif "расписание" in text:
        await show_schedule(update, context)
    else:
        await update.message.reply_text("Не понимаю. Выбери из меню.")


def build_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Напомнить через...", callback_data="remind")],
        [InlineKeyboardButton("✅ Прошел, перейти к...", callback_data="next_or_prev")],
    ])


async def on_lesson_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    # if query.data == "next_lesson":
    #     user_data[user_id]["lesson_index"] += 1
    #     await send_lesson(query.message.chat_id, user_id, context)
    #
    # elif query.data == "prev_lesson":
    #     user_data[user_id]["lesson_index"] -= 1
    #     await send_lesson(query.message.chat_id, user_id, context)

    if query.data == "remind":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Через 12 часов", callback_data="remind_1"),
                InlineKeyboardButton("1д", callback_data="remind_1"),
                InlineKeyboardButton("3д", callback_data="remind_3")
            ],
            [
                InlineKeyboardButton("5 дней", callback_data="remind_5"),
                InlineKeyboardButton("неделю", callback_data="remind_7"),
            ],
            [
                InlineKeyboardButton("2 недели", callback_data="remind_14"),
                InlineKeyboardButton("месяц", callback_data="remind_30")
            ]
        ])
        await query.edit_message_reply_markup(reply_markup=keyboard)

    elif query.data == "next_or_prev":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏮ Вернуться к предыдущем", callback_data="prev_lesson")],
            [InlineKeyboardButton("⏸ Больше не напоминать", callback_data="complete_lesson")],
            [InlineKeyboardButton("✅ Перейти к следующему", callback_data="next_lesson")]
        ])
        await query.edit_message_reply_markup(reply_markup=keyboard)

    elif query.data.startswith("remind_in_"):
        days = int(query.data.split("_")[-1])
        chat_id = query.message.chat_id
        await schedule_reminder(query, chat_id, interval_days=days, context=context)
        await context.bot.send_message(chat_id=chat_id, text=f"📅 Хорошо! Напомню через {days} дней.")


async def schedule_reminder(query, chat_id, interval_days, context):
    reminder_id = 0
    async with async_session() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder:
            await query.edit_message_text("Напоминание не найдено.")
            return

        # Удаляем текущее напоминание
        await session.delete(reminder)

        # Добавляем напоминание на следующий урок
        next_index = reminder.lesson_index + 1
        if next_index < len(lessons):
            new_reminder = Reminder(
                user_id=reminder.user_id,
                lesson_index=next_index,
                remind_at=datetime.now()
            )
            session.add(new_reminder)
            await session.commit()
            await query.edit_message_text(
                f"✅ Урок {reminder.lesson_index + 1} завершён. Следующий добавлен в напоминания.")
        else:
            await session.commit()
            await query.edit_message_text("🎉 Все уроки пройдены!")


async def send_lesson_by_user(user, reminder, context):
    index = reminder.lesson_index
    if 0 <= index < len(lessons):
        lesson = lessons[index]
        msg = f"📘 Пройди урок <a href='{lesson['link']}'>{lesson['title']}</a>"
        keyboard = build_keyboard()
        await context.bot.send_message(chat_id=user.chat_id, text=msg, reply_markup=keyboard,
                                       link_preview_options=LinkPreviewOptions(is_disabled=True),
                                       parse_mode=ParseMode.HTML)


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
    await update.message.reply_text(
        f'Привет {update.effective_user.first_name}, user.name:{update.effective_user.name}, chat.id:{update.effective_chat.id}, {update.effective_chat.effective_name}!',
        reply_markup=main_keyboard)


async def show_all_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📚 Все уроки курса:")
    for idx, lesson in enumerate(lessons):
        msg = f"<a href='{lesson['link']}'>{lesson['title']}</a>"
        keyboard = build_keyboard()
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", show_schedule))
    app.add_handler(CommandHandler("today", show_today_lessons))
    app.add_handler(CommandHandler("help", hello))
    app.add_handler(CommandHandler("all", show_all_lessons))
    app.add_handler(CommandHandler("schedule", show_schedule))
    app.add_handler(CallbackQueryHandler(on_lesson_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    schedule_checker(app)

    await app.initialize()
    await app.start()

    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
