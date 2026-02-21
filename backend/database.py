import aiosqlite
import os

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/muenzbox.db")


async def get_db():
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                switch_coins INTEGER DEFAULT 0,
                switch_coins_weekly INTEGER DEFAULT 2,
                switch_coins_max INTEGER DEFAULT 10,
                tv_coins INTEGER DEFAULT 0,
                tv_coins_weekly INTEGER DEFAULT 2,
                tv_coins_max INTEGER DEFAULT 10,
                allowed_from TEXT DEFAULT '08:00',
                allowed_until TEXT DEFAULT '20:00'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                coins_used INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS coin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
        """)
        await db.commit()
