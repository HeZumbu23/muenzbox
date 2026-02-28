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
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
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
                allowed_until TEXT DEFAULT '20:00',
                weekend_from TEXT DEFAULT '08:00',
                weekend_until TEXT DEFAULT '20:00',
                allowed_periods TEXT DEFAULT '[{"von":"08:00","bis":"20:00"}]',
                weekend_periods TEXT DEFAULT '[{"von":"08:00","bis":"20:00"}]'
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
        # Migrate: weekend columns (v1)
        for col, default in [("weekend_from", "08:00"), ("weekend_until", "20:00")]:
            try:
                await db.execute(
                    f"ALTER TABLE children ADD COLUMN {col} TEXT DEFAULT '{default}'"
                )
                await db.commit()
            except Exception:
                pass

        # Migrate: JSON period columns (v2) – populate from old single-window columns
        import json as _json
        for periods_col, from_col, until_col in [
            ("allowed_periods", "allowed_from", "allowed_until"),
            ("weekend_periods", "weekend_from", "weekend_until"),
        ]:
            col_added = False
            try:
                await db.execute(f"ALTER TABLE children ADD COLUMN {periods_col} TEXT")
                col_added = True
                await db.commit()
            except Exception:
                pass  # Column already exists
            if col_added:
                async with db.execute(f"SELECT id, {from_col}, {until_col} FROM children") as cur:
                    rows = await cur.fetchall()
                for row in rows:
                    periods = _json.dumps([{
                        "von": row[from_col] or "08:00",
                        "bis": row[until_col] or "20:00",
                    }])
                    await db.execute(
                        f"UPDATE children SET {periods_col}=? WHERE id=?",
                        (periods, row["id"]),
                    )
                await db.commit()

        await db.commit()

        # Devices table (v3)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                control_type TEXT NOT NULL,
                identifier TEXT,
                child_id INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
        """)
        await db.commit()

        # Migrate devices (v4): ensure identifier column exists
        try:
            await db.execute("ALTER TABLE devices ADD COLUMN identifier TEXT")
            await db.commit()
        except Exception:
            pass  # column already exists

        # Migrate devices (v5): ensure name column exists (display name separate from identifier)
        # If name doesn't exist yet, add it and copy from identifier as fallback
        col_added = False
        try:
            await db.execute("ALTER TABLE devices ADD COLUMN name TEXT")
            col_added = True
            await db.commit()
        except Exception:
            pass  # column already exists
        if col_added:
            # Populate name from identifier for existing rows
            await db.execute(
                "UPDATE devices SET name = COALESCE(identifier, 'Gerät') WHERE name IS NULL"
            )
            await db.commit()

        # Migrate devices (v6): switch legacy mikrotik TV devices to fritzbox
        await db.execute(
            "UPDATE devices SET control_type='fritzbox' WHERE control_type='mikrotik' AND device_type='tv'"
        )
        await db.commit()

        # Migrate devices (v7): add config column for per-device credentials
        try:
            await db.execute("ALTER TABLE devices ADD COLUMN config TEXT DEFAULT '{}'")
            await db.commit()
        except Exception:
            pass  # column already exists

        # Seed TV device if not present
        async with db.execute("SELECT COUNT(*) as n FROM devices WHERE device_type='tv'") as cur:
            row = await cur.fetchone()
        if row["n"] == 0:
            tv_identifier = os.getenv("MIKROTIK_TV_ADDRESS_LIST_COMMENT", "Fernseher")
            await db.execute(
                "INSERT INTO devices (name, device_type, control_type, identifier) VALUES (?,?,?,?)",
                ("Fernseher", "tv", "fritzbox", tv_identifier),
            )
            await db.commit()
