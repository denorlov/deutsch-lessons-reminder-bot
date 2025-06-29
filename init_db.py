import asyncio
import aiosqlite

DB_FILE = "lessons.db"

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
        print("База данных создана и инициализирована.")

if __name__ == "__main__":
    asyncio.run(init_db())