import asyncio
from datetime import datetime, timedelta, time
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
    {"title": "Lektion 3. Глагол sein (быть)", "link": "https://t.me/c/2054418094/64?thread=58"},
    {"title": "Lektion 4. Тренировка sein. Лексика: прилагательные", "link": "https://t.me/c/2054418094/129?thread=65"},
    {"title": "Lektion 5. Правила чтения: sch, вокализованный r, w, немой h",
     "link": "https://t.me/c/2054418094/71?thread=69"},
    {"title": "Lektion 6. Тренировка sein, рода существительных, лексика",
     "link": "https://t.me/c/2054418094/75?thread=72"},
    {"title": "Lektion 7. Rr", "link": "https://t.me/c/2054418094/83?thread=77"},
    {"title": "Lektion 8. Teil 1. Das Auto ist neu: лексика", "link": "https://t.me/c/2054418094/93?thread=78"},
    {"title": "Lektion 8. Teil 2", "link": "https://t.me/c/2054418094/94?thread=79"},
    {"title": "Lektion 9. Правила чтения: ei, ch, ck", "link": "https://t.me/c/2054418094/95?thread=84"},
    {"title": "Lektion 10. Определенный и неопределенный артикли", "link": "https://t.me/c/2054418094/96?thread=85"},
    {"title": "Lektion 11. Тренировка артиклей", "link": "https://t.me/c/2054418094/119?thread=103"},
    {"title": "Lektion 12. Тренировка", "link": "https://t.me/c/2054418094/120?thread=104"},
    {"title": "Lektion 13. Правила чтения: z, s, ie", "link": "https://t.me/c/2054418094/121?thread=105"},
    {"title": "Lektion 14. Нулевой артикль", "link": "https://t.me/c/2054418094/122?thread=109"},
    {"title": "Lektion 15. Правила чтения: eu, v, ng, nk, -ig, j", "link": "https://t.me/c/2054418094/123?thread=110"},
    {"title": "Lektion 16. Спряжение глаголов", "link": "https://t.me/c/2054418094/124?thread=111"},
    {"title": "Lektion 17. Спряжение глаголов. Тренировка", "link": "https://t.me/c/2054418094/141?thread=115"},
    {"title": "Lektion 18. Тренировка глаголов. Лексика", "link": "https://t.me/c/2054418094/146?thread=116"},
    {"title": "Lektion 19. Новые глаголы", "link": "https://t.me/c/2054418094/150?thread=117"},
    {"title": "Lektion 20. Тренировка всех глаголов", "link": "https://t.me/c/2098391193/38"},
    {"title": "Lektion 21. Akkusativ: неопределенный артикль", "link": "https://t.me/c/2098391193/39"},
    {"title": "Lektion 22. Akkusativ: определенный артикль", "link": "https://t.me/c/2098391193/40"},
    {"title": "Lektion 23. Teil 1. Akkusativ: тренировка", "link": "https://t.me/c/2098391193/41"},
    {"title": "Lektion 23. Teil 2. Akkusativ: тренировка", "link": "https://t.me/c/2098391193/42"},
    {"title": "Lektion 24. Тренировка", "link": "https://t.me/c/2098391193/43"},
    {"title": "Lektion 25. Тренировка", "link": "https://t.me/c/2098391193/44"},
    {"title": "Lektion 26. Неисчисляемые существительные в Akkusativ", "link": "https://t.me/c/2098391193/45"},
    {"title": "Lektion 27. Множественное число", "link": "https://t.me/c/2098391193/46"},
    {"title": "Lektion 28. Множественное число", "link": "https://t.me/c/2098391193/47"},
    {"title": "Lektion 29. Мн. число: тренировка", "link": "https://t.me/c/2098391193/48"},
    {"title": "Lektion 30. Мн. число в Akkusativ", "link": "https://t.me/c/2098391193/49"},
    {"title": "Lektion 31. Суффикс женского рода и мн. число", "link": "https://t.me/c/2098391193/50"},
    {"title": "Lektion 32. Спряжение глаголов на -s, -z, -ß", "link": "https://t.me/c/2098391193/51"},
    {"title": "Lektion 33. Спряжение: дополнение", "link": "https://t.me/c/2098391193/52"},
    {"title": "Lektion 34. Тренировка", "link": "https://t.me/c/2098391193/53"},
    {"title": "Lektion 35. Общие вопросы", "link": "https://t.me/c/2098391193/54"},
    {"title": "Lektion 36. Сильные глаголы с 'а'.", "link": "https://t.me/c/2098391193/55"},
    {"title": "Lektion 37. Сильные глаголы с 'a'. Тренировка", "link": "https://t.me/c/2098391193/56"},
    {"title": "Lektion 38.1 Тренировка сильных глаголов с 'a'", "link": "https://t.me/c/2098391193/57"},
    {"title": "Lektion 38.2. Сильные глаголы с 'e'", "link": "https://t.me/c/2098391193/58"},
    {"title": "Lektion 39. Сильные глаголы с 'e'. Тренировка", "link": "https://t.me/c/2098391193/59"},
    {"title": "Lektion 40. Сильные глаголы с 'e'. Тренировка", "link": "https://t.me/c/2098391193/60"},
    {"title": "Lektion 41. Мини-лекция об изучении иностранного языка", "link": "https://t.me/c/2098391193/61"},
    {"title": "Lektion 42. Shadowing", "link": "https://t.me/c/2098391193/62"},
    {"title": "Lektion 43. Shadowing. Дополнительная тренировка", "link": "https://t.me/c/2098391193/63"},
    {"title": "Lektion 44. Порядок слов", "link": "https://t.me/c/2098391193/64"},
    {"title": "Lektion 45. Порядок слов. Тренировка", "link": "https://t.me/c/2098391193/65"},
    {"title": "Lektion 46. Тренировка обратного порядка слов", "link": "https://t.me/c/2098391193/66"},
    {"title": "Lektion 47. Числа 0-10", "link": "https://t.me/c/2098391193/67"},
    {"title": "Lektion 48. Тренировка числительных", "link": "https://t.me/c/2098391193/68"},
    {"title": "Lektion 49. Глагол haben", "link": "https://t.me/c/2098391193/69"},
    {"title": "Lektion 50. 11-20", "link": "https://t.me/c/2098391193/70"}
]

main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📋 Уроки на сегодня")],
    # todo: реализовать редактирование расписание (один раз в день, два раза в день, какое время?)
    [KeyboardButton("⚙️ Настроить расписание")]
    # todo: показать пройденные уроки (с возможностью поставить напоминалку на через x дней или перейти к этому уроку, тогда все запланирвоанные или проходимые уроки удаляются, остается только выбранный)
], resize_keyboard=True)


# todo: внедрить лексические трениниги

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True)
    schedule = Column(String, default='08:00')


class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    lesson_index = Column(Integer)
    remind_at = Column(DateTime)


def schedule_checker(application):
    # todo:
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
    # todo: если нет ни одного запланированного урока, добавить в reminder первый урок
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(chat_id=chat_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # todo: set to 00:00:00
            reminder = Reminder(user_id=user.id, lesson_index=0, remind_at=datetime.now())
            session.add(reminder)
            await session.commit()

    await show_today_lessons(update, context)


async def show_today_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()

        if not user:
            await start(update, context)

        result = await session.execute(
            select(Reminder.lesson_index).where(
                Reminder.user_id == user.id,
                Reminder.remind_at <= datetime.now()
            )
        )

        indices = sorted(set(row[0] for row in result.fetchall()))
        logger.info(f"indices: {indices}")

        if indices:
            await context.bot.send_message(chat_id=chat_id, text="📋 Уроки на сегодня:")
            for idx in indices:
                if 0 <= idx < len(lessons):
                    await show_lesson(update, context, idx)
        else:
            await update.message.reply_text("На сегодня уроков нет.")
            await show_planned_lessons(update, context)


async def show_lesson(update, context, lesson_id):
    chat_id = update.effective_chat.id
    lesson = lessons[lesson_id]
    msg = f"<a href='{lesson['link']}'>{lesson['title']}</a>"
    keyboard = build_keyboard(lesson_id)
    await context.bot.send_message(chat_id=chat_id,
                                   text=msg,
                                   parse_mode=ParseMode.HTML,
                                   reply_markup=keyboard,
                                   link_preview_options=LinkPreviewOptions(is_disabled=True))


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Пока редактирование не доступно")


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


def build_keyboard(lesson_id):
    logger.info(f"build_keyboard(lesson_id={lesson_id})")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Прошел, к следующему", callback_data=f"next_lesson_{lesson_id}"),
            InlineKeyboardButton("🔁 Отложить на...", callback_data=f"remind_1_{lesson_id}")
        ],
    ])


async def on_lesson_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"query.data={query.data})")

    await query.answer()

    if query.data.startswith("remind_1"):
        query_request_data = query.data.split("_")
        lesson_id = int(query_request_data[-1])
        logger.info(f"lesson_id={lesson_id})")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅", callback_data=f"next_lesson_{lesson_id}"),
                InlineKeyboardButton("1 день", callback_data=f"remind_2_1_{lesson_id}"),
                InlineKeyboardButton("2 дня", callback_data=f"remind_2_2_{lesson_id}"),
                InlineKeyboardButton("3 дня", callback_data=f"remind_2_3_{lesson_id}")
            ],
            # [
            #     InlineKeyboardButton("5 дней", callback_data=f"remind_2_5_{lesson_id}"),
            #     InlineKeyboardButton("неделю", callback_data=f"remind_2_7_{lesson_id}"),
            # ],
            # [
            #     InlineKeyboardButton("2 недели", callback_data=f"remind_2_14_{lesson_id}"),
            #     InlineKeyboardButton("месяц", callback_data=f"remind_2_30_{lesson_id}")
            # ]
        ])
        await query.edit_message_reply_markup(reply_markup=keyboard)

    elif query.data.startswith("remind_2"):
        query_request_data = query.data.split("_")
        days = int(query_request_data[-2])
        logger.info(f"days={days})")
        lesson_id = int(query_request_data[-1])
        logger.info(f"lesson_id={lesson_id})")
        await update_reminder_to_next_time(update, lesson_id, interval_days=days, context=context)

    elif query.data.startswith("next_lesson_"):
        query_request_data = query.data.split("_")
        lesson_id = int(query_request_data[-1])
        logger.info(f"lesson_id={lesson_id})")
        await update_reminder_to_next_lesson(update, lesson_id=lesson_id, context=context)

    elif query.data.startswith("new_reminder_today"):
        query_request_data = query.data.split("_")
        lesson_id = int(query_request_data[-1])
        logger.info(f"lesson_id={lesson_id})")
        await set_reminder_for_today(update, lesson_id, context)

    elif query.data.startswith("move_lesson_to_today"):
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id, f"Введите номер урока, который вы хотите перенести на сегодня:")


async def update_reminder_to_next_lesson(update, lesson_id, context):
    logger.info(f"update_reminder_to_next_lesson(lesson_id={lesson_id})")
    chat_id = update.effective_chat.id
    async with (async_session() as session):
        result = await session.execute(
            select(Reminder)
            .join(User)
            .where(
                User.chat_id == chat_id,
                Reminder.lesson_index == lesson_id
            )
        )
        reminder = result.scalar_one_or_none()
        logger.info(f"result: {reminder}")
        if not reminder:
            # todo: создать reminder
            await context.bot.send_message(chat_id=chat_id, text="Напоминание не найдено.")

        next_index = reminder.lesson_index + 1
        if next_index < len(lessons):
            # Добавляем напоминание на следующий урок
            reminder.lesson_index = next_index
            reminder.remind_at = datetime.combine(datetime.today().date(), time.min)
            await session.commit()
            await context.bot.send_message(chat_id, f"Урок завершён. Следующий добавлен в напоминания.", ParseMode.HTML)
            await show_today_lessons(update, context)

        else:
            # Удаляем текущее напоминание
            await session.delete(reminder)
            await session.commit()
            await context.bot.send_message(chat_id=chat_id, text="🎉 Все уроки пройдены!")


async def delete_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("Пользователь не найден.")
            return

        await session.execute(
            delete(Reminder).where(Reminder.user_id == user.id)
        )
        await session.commit()

        await update.message.reply_text("🗑️ Все напоминания удалены.")


def format_lesson(lesson_id):
    lesson = lessons[lesson_id]
    return f"<a href='{lesson['link']}'>{lesson['title']}</a>"


months_ru = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


def format_date(datetime):
    return f"{datetime.day} {months_ru[datetime.month - 1]} {datetime.year}"


async def set_reminder_for_today(update, lesson_id, context):
    logger.info(f"set_reminder_for_today(lesson_id={lesson_id})")
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("Пользователь не найден.")
            return

        await session.execute(
            delete(Reminder).where(Reminder.user_id == user.id and Reminder.lesson_index == lesson_id)
        )
        await session.commit()

        date = datetime.combine(datetime.today().date(), time.min)
        reminder = Reminder(user_id=user.id, lesson_index=lesson_id, remind_at=date)
        session.add(reminder)
        await session.commit()

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{format_lesson(reminder.lesson_index)} добавлен в напоминания.",
            parse_mode=ParseMode.HTML
        )

    await show_today_lessons(update, context)


async def update_reminder_to_next_time(update, lesson_id, interval_days, context):
    logger.info(f"update_reminder_to_next_lesson(lesson_id={lesson_id})")
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(
            select(Reminder)
            .join(User)
            .where(
                User.chat_id == chat_id,
                Reminder.lesson_index == lesson_id
            )
        )
        reminder = result.scalar_one_or_none()
        logger.info(f"result: {reminder}")
        if not reminder:
            # todo: создать reminder
            await context.bot.send_message(chat_id=chat_id, text="Напоминание не найдено.")

        # меняем дату напоминания
        now = datetime.combine(datetime.today().date(), time.min)
        reminder.remind_at = now + timedelta(days=interval_days)
        await session.commit()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📅 Хорошо! Напомню про\n {format_lesson(reminder.lesson_index)} {format_date(reminder.remind_at)}.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )


async def send_lesson_by_user(user, reminder, context):
    lesson_id = reminder.lesson_index
    keyboard = build_keyboard(lesson_id)
    await context.bot.send_message(chat_id=user.chat_id, text=format_lesson(lesson_id), reply_markup=keyboard,
                                   link_preview_options=LinkPreviewOptions(is_disabled=True),
                                   parse_mode=ParseMode.HTML)


async def check_reminders(context: CallbackContext):
    now = datetime.now()
    async with async_session() as session:
        result = await session.execute(select(Reminder).join(User).where(Reminder.remind_at <= now))
        reminders = result.scalars().all()
        for reminder in reminders:
            user = await session.get(User, reminder.user_id)
            # todo: сгруппировать по пользователю, каждому пользователю отправлять только одно сообщение Пройди урок(и)
            await context.bot.send_message(chat_id=user.chat_id, text=f"📘 Пройди урок(и):\n ",
                                           parse_mode=ParseMode.HTML)
            await send_lesson_by_user(user, reminder, context)
            await session.commit()


async def diag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f'Привет, {update.effective_user.name}! '
        f'chat.id:{update.effective_chat.id}, '
        f'chat.effective_name: {update.effective_chat.effective_name}!',
        reply_markup=main_keyboard)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()
        if not user:
            await start(update, context)
        await update.message.reply_text(
            f"Расписание: user.id={user.id}, chat_id:{user.chat_id}, schedule: {user.schedule}")

    for job in scheduler.get_jobs():
        await update.message.reply_text(
            f"job id:{job.id}, name:{job.name}, trigger:{job.trigger}, next run time:{job.next_run_time}")


async def show_all_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"📚 Все уроки курса:"
    for lesson_id, lesson in enumerate(lessons):
        msg = f"\n{lesson_id}. <a href='{lesson['link']}'>{lesson['title']}</a>"

    keyboard = all_lessons_keyboard(lesson_id)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)

def all_lessons_keyboard(lesson_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Перенести урок в напоминания", callback_data=f"move_lesson_to_today"),
        ],
    ])

async def show_planned_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    async with async_session() as session:
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalar_one_or_none()

        if not user:
            # todo: создать user и reminder
            await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start")
            return

        result = await session.execute(
            select(Reminder).where(
                Reminder.user_id == user.id,
                Reminder.remind_at >= datetime.now()
            )
        )
        logger.info(f"result: {result}")
        reminders = result.scalars().all()
        logger.info(f"reminders: {reminders}")

        if not reminders:
            await update.message.reply_text("Запланированных уроков нет.")
            return

        await update.message.reply_text("📋 Запланированные уроки:")
        for reminder in reminders:
            if 0 <= reminder.lesson_index < len(lessons):
                lesson = lessons[reminder.lesson_index]
                msg = f"{format_date(reminder.remind_at)} <a href='{lesson['link']}'>{lesson['title']}</a>"
                keyboard = future_lesson_keyboard(reminder.lesson_index)
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)


def future_lesson_keyboard(lesson_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Пройти сегодня", callback_data=f"new_reminder_today_lesson_{lesson_id}"),
        ],
    ])


async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", show_schedule))
    app.add_handler(CommandHandler("help", diag))

    app.add_handler(CommandHandler("all", show_all_lessons))
    app.add_handler(CommandHandler("today", show_today_lessons))

    app.add_handler(CommandHandler("planned", show_planned_lessons))
    app.add_handler(CommandHandler("reminders", show_planned_lessons))
    app.add_handler(CommandHandler("future", show_planned_lessons))
    app.add_handler(CommandHandler("delete", delete_reminders))

    app.add_handler(CallbackQueryHandler(on_lesson_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    schedule_checker(app)

    # todo: remove main app menu
    await app.initialize()
    await app.start()

    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
