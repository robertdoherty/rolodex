"""SQLite storage layer for the Rolodex system."""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from config import DATABASE_PATH, DATA_DIR, PersonType, Tag
from models import Followup, Interaction, Person


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            name TEXT PRIMARY KEY,
            current_company TEXT NOT NULL,
            type TEXT DEFAULT '',
            background TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            company_industry TEXT DEFAULT '',
            company_revenue TEXT DEFAULT '',
            company_headcount TEXT DEFAULT '',
            state_of_play TEXT DEFAULT '',
            last_delta TEXT DEFAULT ''
        )
    """)

    # Migrate: add columns that may be missing from older schemas
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(persons)").fetchall()}
    for col, default in [
        ("linkedin_url", "''"),
        ("company_industry", "''"),
        ("company_revenue", "''"),
        ("company_headcount", "''"),
    ]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE persons ADD COLUMN {col} TEXT DEFAULT {default}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            date TEXT NOT NULL,
            transcript TEXT NOT NULL,
            takeaways TEXT NOT NULL,
            tags TEXT NOT NULL,
            FOREIGN KEY (person_name) REFERENCES persons(name)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_interactions_person
        ON interactions(person_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_persons_type
        ON persons(type)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS connections (
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            PRIMARY KEY (person_a, person_b),
            FOREIGN KEY (person_a) REFERENCES persons(name),
            FOREIGN KEY (person_b) REFERENCES persons(name),
            CHECK (person_a < person_b)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_connections_b
        ON connections(person_b)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            interaction_id INTEGER NOT NULL,
            date_slug TEXT NOT NULL,
            item TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            FOREIGN KEY (person_name) REFERENCES persons(name),
            FOREIGN KEY (interaction_id) REFERENCES interactions(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_followups_person
        ON followups(person_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_followups_person_status
        ON followups(person_name, status)
    """)

    conn.commit()
    conn.close()


def create_person(
    name: str,
    current_company: str,
    person_type: Optional[PersonType] = None,
    background: str = "",
    linkedin_url: str = "",
    company_industry: str = "",
    company_revenue: str = "",
    company_headcount: str = "",
    connections: list[str] = None,
) -> Person:
    """Create a new person in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO persons (name, current_company, type, background, linkedin_url, company_industry, company_revenue, company_headcount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, current_company, person_type.value if person_type else "", background, linkedin_url, company_industry, company_revenue, company_headcount),
    )

    for other in (connections or []):
        a, b = sorted([name, other])
        cursor.execute("INSERT OR IGNORE INTO connections (person_a, person_b) VALUES (?, ?)", (a, b))

    conn.commit()
    conn.close()

    return Person(
        name=name,
        current_company=current_company,
        type=person_type,
        background=background,
        linkedin_url=linkedin_url,
        company_industry=company_industry,
        company_revenue=company_revenue,
        company_headcount=company_headcount,
        connections=sorted(connections or []),
    )


def delete_person(name: str) -> bool:
    """Delete a person and their interactions from the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM followups WHERE person_name = ?", (name,))
    cursor.execute("DELETE FROM connections WHERE person_a = ? OR person_b = ?", (name, name))
    cursor.execute("DELETE FROM interactions WHERE person_name = ?", (name,))
    cursor.execute("DELETE FROM persons WHERE name = ?", (name,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()
    return deleted


def _fetch_connections(cursor: sqlite3.Cursor, name: str) -> list[str]:
    """Fetch sorted list of connected person names (internal helper)."""
    cursor.execute(
        "SELECT person_a, person_b FROM connections WHERE person_a = ? OR person_b = ?",
        (name, name),
    )
    return sorted(
        r["person_b"] if r["person_a"] == name else r["person_a"]
        for r in cursor.fetchall()
    )


def add_connection(name_a: str, name_b: str) -> None:
    """Add a connection between two persons."""
    a, b = sorted([name_a, name_b])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO connections (person_a, person_b) VALUES (?, ?)", (a, b))
    conn.commit()
    conn.close()


def get_connections(name: str) -> list[str]:
    """Get sorted list of connected person names."""
    conn = get_connection()
    cursor = conn.cursor()
    result = _fetch_connections(cursor, name)
    conn.close()
    return result


def remove_connection(name_a: str, name_b: str) -> bool:
    """Remove a connection between two persons. Returns True if a row was deleted."""
    a, b = sorted([name_a, name_b])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM connections WHERE person_a = ? AND person_b = ?", (a, b))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_person(name: str) -> Optional[Person]:
    """Get a person by name."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM persons WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return None

    cursor.execute(
        "SELECT id FROM interactions WHERE person_name = ? ORDER BY date",
        (name,),
    )
    interaction_ids = [r["id"] for r in cursor.fetchall()]

    connections = _fetch_connections(cursor, name)

    conn.close()

    return Person.from_dict(dict(row), interaction_ids, connections)


def list_persons(type_filter: Optional[PersonType] = None) -> list[Person]:
    """List all persons, optionally filtered by type."""
    conn = get_connection()
    cursor = conn.cursor()

    if type_filter:
        cursor.execute("SELECT * FROM persons WHERE type = ?", (type_filter.value,))
    else:
        cursor.execute("SELECT * FROM persons")

    persons = []
    for row in cursor.fetchall():
        cursor.execute(
            "SELECT id FROM interactions WHERE person_name = ? ORDER BY date",
            (row["name"],),
        )
        interaction_ids = [r["id"] for r in cursor.fetchall()]
        connections = _fetch_connections(cursor, row["name"])
        persons.append(Person.from_dict(dict(row), interaction_ids, connections))

    conn.close()
    return persons


def update_person_state(
    name: str,
    state_of_play: str,
    last_delta: str,
) -> None:
    """Update a person's state_of_play and last_delta."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE persons
        SET state_of_play = ?, last_delta = ?
        WHERE name = ?
        """,
        (state_of_play, last_delta, name),
    )

    conn.commit()
    conn.close()


def update_person_background(name: str, background: str) -> None:
    """Update a person's background."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE persons SET background = ? WHERE name = ?",
        (background, name),
    )

    conn.commit()
    conn.close()


def delete_interaction(interaction_id: int) -> bool:
    """Delete an interaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM followups WHERE interaction_id = ?", (interaction_id,))
    cursor.execute("DELETE FROM interactions WHERE id = ?", (interaction_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()
    return deleted


def create_interaction(
    person_name: str,
    date: datetime,
    transcript: dict,
    takeaways: list[str],
    tags: list[Tag],
) -> Interaction:
    """Create a new interaction record."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO interactions (person_name, date, transcript, takeaways, tags)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            person_name,
            date.isoformat(),
            json.dumps(transcript),
            json.dumps(takeaways),
            json.dumps([t.value for t in tags]),
        ),
    )

    interaction_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return Interaction(
        id=interaction_id,
        person_name=person_name,
        date=date,
        transcript=transcript,
        takeaways=takeaways,
        tags=tags,
    )


def get_interaction(interaction_id: int) -> Optional[Interaction]:
    """Get an interaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM interactions WHERE id = ?", (interaction_id,))
    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return Interaction(
        id=row["id"],
        person_name=row["person_name"],
        date=datetime.fromisoformat(row["date"]),
        transcript=json.loads(row["transcript"]),
        takeaways=json.loads(row["takeaways"]),
        tags=[Tag(t) for t in json.loads(row["tags"])],
    )


def get_interactions(person_name: str) -> list[Interaction]:
    """Get all interactions for a person."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM interactions WHERE person_name = ? ORDER BY date",
        (person_name,),
    )

    interactions = []
    for row in cursor.fetchall():
        interactions.append(
            Interaction(
                id=row["id"],
                person_name=row["person_name"],
                date=datetime.fromisoformat(row["date"]),
                transcript=json.loads(row["transcript"]),
                takeaways=json.loads(row["takeaways"]),
                tags=[Tag(t) for t in json.loads(row["tags"])],
            )
        )

    conn.close()
    return interactions


def get_interactions_by_date(person_name: str, date_str: str) -> list[Interaction]:
    """Get interactions for a person on a specific date, ordered by id."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM interactions WHERE person_name = ? AND date LIKE ? ORDER BY id",
        (person_name, f"{date_str}%"),
    )

    interactions = []
    for row in cursor.fetchall():
        interactions.append(
            Interaction(
                id=row["id"],
                person_name=row["person_name"],
                date=datetime.fromisoformat(row["date"]),
                transcript=json.loads(row["transcript"]),
                takeaways=json.loads(row["takeaways"]),
                tags=[Tag(t) for t in json.loads(row["tags"])],
            )
        )

    conn.close()
    return interactions


def get_interactions_by_tag(tag: Tag) -> list[Interaction]:
    """Get all interactions with a specific tag."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM interactions ORDER BY date")

    interactions = []
    for row in cursor.fetchall():
        tags = json.loads(row["tags"])
        if tag.value in tags:
            interactions.append(
                Interaction(
                    id=row["id"],
                    person_name=row["person_name"],
                    date=datetime.fromisoformat(row["date"]),
                    transcript=json.loads(row["transcript"]),
                    takeaways=json.loads(row["takeaways"]),
                    tags=[Tag(t) for t in tags],
                )
            )

    conn.close()
    return interactions


def create_followups(
    person_name: str,
    interaction_id: int,
    date_slug: str,
    items: list[str],
) -> list[Followup]:
    """Bulk-create followup items for an interaction."""
    if not items:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    followups = []
    for item in items:
        cursor.execute(
            """
            INSERT INTO followups (person_name, interaction_id, date_slug, item, status)
            VALUES (?, ?, ?, ?, 'open')
            """,
            (person_name, interaction_id, date_slug, item),
        )
        followups.append(Followup(
            id=cursor.lastrowid,
            person_name=person_name,
            interaction_id=interaction_id,
            date_slug=date_slug,
            item=item,
            status="open",
        ))

    conn.commit()
    conn.close()
    return followups


def get_open_followups(person_name: str) -> list[Followup]:
    """Get open followup items for a person, ordered by id."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM followups WHERE person_name = ? AND status = 'open' ORDER BY id",
        (person_name,),
    )

    followups = []
    for row in cursor.fetchall():
        followups.append(Followup(
            id=row["id"],
            person_name=row["person_name"],
            interaction_id=row["interaction_id"],
            date_slug=row["date_slug"],
            item=row["item"],
            status=row["status"],
        ))

    conn.close()
    return followups


def complete_followup(followup_id: int) -> Optional[Followup]:
    """Mark a followup as complete. Returns the Followup or None if not found."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM followups WHERE id = ?", (followup_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return None

    cursor.execute(
        "UPDATE followups SET status = 'complete' WHERE id = ?",
        (followup_id,),
    )
    conn.commit()

    followup = Followup(
        id=row["id"],
        person_name=row["person_name"],
        interaction_id=row["interaction_id"],
        date_slug=row["date_slug"],
        item=row["item"],
        status="complete",
    )

    conn.close()
    return followup
