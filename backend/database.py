"""SQLite storage layer for the Rolodex system."""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from config import DATABASE_PATH, DATA_DIR, PersonType, Tag
from models import Interaction, Person


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
    )


def delete_person(name: str) -> bool:
    """Delete a person and their interactions from the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM interactions WHERE person_name = ?", (name,))
    cursor.execute("DELETE FROM persons WHERE name = ?", (name,))
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

    conn.close()

    return Person.from_dict(dict(row), interaction_ids)


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
        persons.append(Person.from_dict(dict(row), interaction_ids))

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
