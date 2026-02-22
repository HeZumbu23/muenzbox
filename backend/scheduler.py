"""
APScheduler tasks:
- Saturday 00:00: Weekly coin refill for all children
- Every minute: End expired active sessions
"""
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import aiosqlite
from database import DATABASE_PATH
from adapters import mikrotik_direct, nintendo

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def weekly_coin_refill():
    """Every Saturday at 00:00: coins = min(coins + weekly, max) per child."""
    logger.info("Scheduler: Wöchentliche Münz-Aufladung gestartet")
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM children") as cursor:
            children = await cursor.fetchall()

        for child in children:
            new_switch = min(
                child["switch_coins"] + child["switch_coins_weekly"],
                child["switch_coins_max"],
            )
            new_tv = min(
                child["tv_coins"] + child["tv_coins_weekly"],
                child["tv_coins_max"],
            )

            await db.execute(
                "UPDATE children SET switch_coins=?, tv_coins=? WHERE id=?",
                (new_switch, new_tv, child["id"]),
            )

            switch_delta = new_switch - child["switch_coins"]
            tv_delta = new_tv - child["tv_coins"]

            if switch_delta > 0:
                await db.execute(
                    "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (?,?,?,?,?)",
                    (child["id"], "switch", switch_delta, "weekly_refill", now),
                )
            if tv_delta > 0:
                await db.execute(
                    "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (?,?,?,?,?)",
                    (child["id"], "tv", tv_delta, "weekly_refill", now),
                )

        await db.commit()
    logger.info("Scheduler: Wöchentliche Aufladung abgeschlossen (%d Kinder)", len(children))


async def expire_sessions():
    """Every minute: find active sessions that have expired and close them."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE status='active' AND ends_at <= ?", (now,)
        ) as cursor:
            expired = await cursor.fetchall()

        for session in expired:
            await db.execute(
                "UPDATE sessions SET status='completed' WHERE id=?",
                (session["id"],),
            )
            logger.info(
                "Scheduler: Session %d (%s) für Kind %d abgelaufen",
                session["id"],
                session["type"],
                session["child_id"],
            )
            # Disable hardware
            if session["type"] == "tv":
                await mikrotik_direct.tv_sperren()
            elif session["type"] == "switch":
                await nintendo.switch_sperren()

        if expired:
            await db.commit()


def start_scheduler():
    _scheduler.add_job(
        weekly_coin_refill,
        CronTrigger(day_of_week="sat", hour=0, minute=0),
        id="weekly_refill",
        replace_existing=True,
    )
    _scheduler.add_job(
        expire_sessions,
        CronTrigger(minute="*"),
        id="expire_sessions",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler gestartet")
