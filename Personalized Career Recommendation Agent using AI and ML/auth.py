"""MySQL-backed account registration and authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

DB_PATH = Path(__file__).with_name("career_agent.db")
DATABASE_BACKEND = os.environ.get("CAREERAI_DB_BACKEND", "mysql").casefold()
HASH_NAME = "sha256"
HASH_ITERATIONS = 600_000
SALT_BYTES = 16
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@contextmanager
def _connect() -> Generator[Any, None, None]:
    if DATABASE_BACKEND == "sqlite":
        connection = sqlite3.connect(DB_PATH, timeout=10)
        connection.row_factory = sqlite3.Row
    elif DATABASE_BACKEND == "mysql":
        import mysql.connector

        required_settings = (
            "CAREERAI_DB_USER",
            "CAREERAI_DB_PASSWORD",
            "CAREERAI_DB_DATABASE",
        )
        missing_settings = [
            setting for setting in required_settings if not os.environ.get(setting)
        ]
        if missing_settings:
            raise RuntimeError(
                "MySQL configuration is incomplete. Set CAREERAI_DB_HOST, "
                "CAREERAI_DB_USER, CAREERAI_DB_PASSWORD, and "
                "CAREERAI_DB_DATABASE."
            )
        connection = mysql.connector.connect(
            host=os.environ.get("CAREERAI_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("CAREERAI_DB_PORT", "3306")),
            user=os.environ["CAREERAI_DB_USER"],
            password=os.environ["CAREERAI_DB_PASSWORD"],
            database=os.environ["CAREERAI_DB_DATABASE"],
        )
    else:
        raise RuntimeError("CAREERAI_DB_BACKEND must be 'mysql' or 'sqlite'.")

    try:
        if DATABASE_BACKEND == "sqlite":
            with connection:
                yield connection
        else:
            yield connection
            connection.commit()
    except Exception:
        if DATABASE_BACKEND == "mysql":
            connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the accounts table if it does not already exist."""
    with _connect() as connection:
        if DATABASE_BACKEND == "sqlite":
            _execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )
            _execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS student_profiles (
                    account_id INTEGER PRIMARY KEY,
                    education_level TEXT NOT NULL,
                    field_of_study TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    interests_json TEXT NOT NULL,
                    interested_roles_json TEXT NOT NULL DEFAULT '[]',
                    experience_years INTEGER NOT NULL,
                    career_goal TEXT NOT NULL,
                    preferred_location TEXT NOT NULL DEFAULT 'Remote',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )
                """,
            )
            profile_columns = {
                row["name"]
                for row in _execute(connection, "PRAGMA table_info(student_profiles)")
            }
        else:
            _execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(320) NOT NULL UNIQUE,
                    password_hash CHAR(64) NOT NULL,
                    password_salt CHAR(32) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4
                """,
            )
            _execute(
                connection,
                """
                CREATE TABLE IF NOT EXISTS student_profiles (
                    account_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
                    education_level VARCHAR(100) NOT NULL,
                    field_of_study VARCHAR(255) NOT NULL,
                    skills_json LONGTEXT NOT NULL,
                    interests_json LONGTEXT NOT NULL,
                    interested_roles_json LONGTEXT NOT NULL DEFAULT ('[]'),
                    experience_years INTEGER NOT NULL,
                    career_goal TEXT NOT NULL,
                    preferred_location VARCHAR(255) NOT NULL DEFAULT 'Remote',
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4
                """,
            )
            profile_columns = {
                row["name"]
                for row in _execute(
                    connection,
                    """
                    SELECT COLUMN_NAME AS name
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'student_profiles'
                    """,
                )
            }
        if "preferred_location" not in profile_columns:
            _execute(
                connection,
                "ALTER TABLE student_profiles "
                "ADD COLUMN preferred_location "
                + (
                    "TEXT NOT NULL DEFAULT 'Remote'"
                    if DATABASE_BACKEND == "sqlite"
                    else "VARCHAR(255) NOT NULL DEFAULT 'Remote'"
                ),
            )
        if "interested_roles_json" not in profile_columns:
            _execute(
                connection,
                "ALTER TABLE student_profiles "
                "ADD COLUMN interested_roles_json "
                + (
                    "TEXT NOT NULL DEFAULT '[]'"
                    if DATABASE_BACKEND == "sqlite"
                    else "LONGTEXT NOT NULL"
                ),
            )


def validate_registration(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> str | None:
    """Return a user-facing validation error, or None when input is valid."""
    if not full_name.strip():
        return "Enter your full name."
    if not EMAIL_PATTERN.fullmatch(email.strip()):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if password != confirm_password:
        return "Passwords do not match."
    return None


def create_account(full_name: str, email: str, password: str) -> bool:
    """Create an account. Return False if the email is already registered."""
    salt = secrets.token_bytes(SALT_BYTES)
    password_hash = hashlib.pbkdf2_hmac(
        HASH_NAME, password.encode("utf-8"), salt, HASH_ITERATIONS
    )
    try:
        with _connect() as connection:
            _execute(
                connection,
                """
                INSERT INTO accounts (full_name, email, password_hash, password_salt)
                VALUES (?, ?, ?, ?)
                """,
                (
                    full_name.strip(),
                    email.strip().casefold(),
                    password_hash.hex(),
                    salt.hex(),
                ),
            )
    except Exception as error:
        if not _is_duplicate_error(error):
            raise
        with _connect() as connection:
            existing_account = _execute(
                connection,
                "SELECT 1 FROM accounts WHERE email = ?",
                (email.strip().casefold(),),
            ).fetchone()
        if existing_account:
            return False
        raise
    return True


def authenticate(email: str, password: str) -> dict[str, str] | None:
    """Return the account's public profile when credentials match."""
    with _connect() as connection:
        account = _execute(
            connection,
            "SELECT id, full_name, email, password_hash, password_salt "
            "FROM accounts WHERE email = ?",
            (email.strip().casefold(),),
        ).fetchone()

    if account is None:
        return None

    candidate_hash = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        bytes.fromhex(account["password_salt"]),
        HASH_ITERATIONS,
    )
    if not hmac.compare_digest(candidate_hash.hex(), account["password_hash"]):
        return None

    return {
        "id": str(account["id"]),
        "full_name": account["full_name"],
        "email": account["email"],
    }


def get_student_profile(account_id: str) -> dict[str, object] | None:
    """Load a student's saved profile."""
    with _connect() as connection:
        profile = _execute(
            connection,
            """
            SELECT education_level, field_of_study, skills_json, interests_json,
                   interested_roles_json, experience_years, career_goal,
                   preferred_location
            FROM student_profiles
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()

    if profile is None:
        return None

    return {
        "education_level": profile["education_level"],
        "field_of_study": profile["field_of_study"],
        "skills": json.loads(profile["skills_json"]),
        "interests": json.loads(profile["interests_json"]),
        "interested_roles": json.loads(profile["interested_roles_json"]),
        "experience_years": profile["experience_years"],
        "career_goal": profile["career_goal"],
        "preferred_location": profile["preferred_location"],
    }


def save_student_profile(
    account_id: str,
    education_level: str,
    field_of_study: str,
    skills: list[str],
    interests: list[str],
    experience_years: int,
    career_goal: str,
    preferred_location: str = "Remote",
    interested_roles: list[str] | None = None,
) -> None:
    """Create or update the profile belonging to a student account."""
    with _connect() as connection:
        upsert = (
            "ON CONFLICT(account_id) DO UPDATE SET"
            if DATABASE_BACKEND == "sqlite"
            else "ON DUPLICATE KEY UPDATE"
        )
        _execute(
            connection,
            """
            INSERT INTO student_profiles (
                account_id, education_level, field_of_study, skills_json,
                interests_json, interested_roles_json, experience_years, career_goal,
                preferred_location, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """ + upsert + """
                education_level = excluded.education_level,
                field_of_study = excluded.field_of_study,
                skills_json = excluded.skills_json,
                interests_json = excluded.interests_json,
                interested_roles_json = excluded.interested_roles_json,
                experience_years = excluded.experience_years,
                career_goal = excluded.career_goal,
                preferred_location = excluded.preferred_location,
                updated_at = CURRENT_TIMESTAMP
            """ if DATABASE_BACKEND == "sqlite" else """
            INSERT INTO student_profiles (
                account_id, education_level, field_of_study, skills_json,
                interests_json, interested_roles_json, experience_years, career_goal,
                preferred_location, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """ + upsert + """
                education_level = VALUES(education_level),
                field_of_study = VALUES(field_of_study),
                skills_json = VALUES(skills_json),
                interests_json = VALUES(interests_json),
                interested_roles_json = VALUES(interested_roles_json),
                experience_years = VALUES(experience_years),
                career_goal = VALUES(career_goal),
                preferred_location = VALUES(preferred_location),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                account_id,
                education_level,
                field_of_study.strip(),
                json.dumps(skills),
                json.dumps(interests),
                json.dumps(interested_roles or []),
                experience_years,
                career_goal.strip(),
                preferred_location.strip() or "Remote",
            ),
        )


def _execute(
    connection: Any,
    statement: str,
    parameters: tuple[object, ...] = (),
):
    if DATABASE_BACKEND == "sqlite":
        return connection.execute(statement, parameters)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(statement.replace("?", "%s"), parameters)
    return cursor


def _is_duplicate_error(error: Exception) -> bool:
    if DATABASE_BACKEND == "sqlite":
        return isinstance(error, sqlite3.IntegrityError)
    return getattr(error, "errno", None) == 1062
