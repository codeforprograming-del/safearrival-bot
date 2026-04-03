import aiosqlite

DB_PATH = "safearrival.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                safe_word  TEXT DEFAULT 'pizza'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                contact_id INTEGER,
                name       TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS journeys (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                destination TEXT,
                deadline    REAL,
                location    TEXT,
                active      INTEGER DEFAULT 1
            )
        """)
        await db.commit()

async def add_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()

async def add_contact(user_id, contact_id, name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO contacts (user_id, contact_id, name) VALUES (?, ?, ?)",
            (user_id, contact_id, name)
        )
        await db.commit()

async def get_contacts(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT contact_id, name FROM contacts WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_contacts_with_id(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, contact_id, name FROM contacts WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def delete_contact(row_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM contacts WHERE id = ?",
            (row_id,)
        )
        await db.commit()

async def delete_all_contacts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM contacts WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def create_journey(user_id, destination, deadline_ts, location=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO journeys (user_id, destination, deadline, location) VALUES (?, ?, ?, ?)",
            (user_id, destination, deadline_ts, location)
        )
        await db.commit()
        return cursor.lastrowid

async def deactivate_journey(journey_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE journeys SET active = 0 WHERE id = ?",
            (journey_id,)
        )
        await db.commit()

async def get_active_journey(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, destination, deadline FROM journeys WHERE user_id = ? AND active = 1",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def update_location(user_id, lat, lon):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE journeys SET location = ? WHERE user_id = ? AND active = 1",
            (f"{lat},{lon}", user_id)
        )
        await db.commit()

async def get_journey_location(journey_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT location FROM journeys WHERE id = ?",
            (journey_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_safe_word(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT safe_word FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "pizza"

async def set_safe_word(user_id, word):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET safe_word = ? WHERE user_id = ?",
            (word, user_id)
        )
        await db.commit()