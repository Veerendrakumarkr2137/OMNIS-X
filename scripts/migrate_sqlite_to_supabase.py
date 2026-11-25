"""Copy an existing OMNIS-X SQLite database into an empty private schema."""

import argparse
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import Base, Login, POSTGRES_SCHEMA, State, database_engine


def migrate(source_path):
    source = create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True),
    )
    target = database_engine()
    if target.dialect.name != "postgresql":
        raise ValueError("Configure a PostgreSQL DATABASE_URL first.")
    tables = [
        table for table in Base.metadata.sorted_tables if table != Login.__table__
    ]
    counts = {}
    try:
        with source.connect() as local, target.begin() as remote:
            local.exec_driver_sql("BEGIN")
            remote.exec_driver_sql("SELECT pg_advisory_xact_lock(74810025)")
            if any(
                remote.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            ):
                raise ValueError("The target schema already contains records.")
            if local.scalar(select(func.count()).select_from(State.__table__)) != 1:
                raise ValueError("The source is missing initialized campus data.")
            for table in tables:
                source_rows = local.execute(select(table)).mappings()
                counts[table.name] = 0
                while batch := source_rows.fetchmany(500):
                    remote.execute(table.insert(), [dict(row) for row in batch])
                    counts[table.name] += len(batch)
                if (
                    remote.scalar(select(func.count()).select_from(table))
                    != counts[table.name]
                ):
                    raise ValueError(f"Row count mismatch in {table.name}.")
                primary = table.autoincrement_column
                if primary is not None and counts[table.name]:
                    maximum = remote.scalar(select(func.max(primary)))
                    remote.execute(
                        text(
                            "SELECT setval(pg_get_serial_sequence(:table, :column), :maximum)"
                        ),
                        dict(
                            table=f"{POSTGRES_SCHEMA}.{table.name}",
                            column=primary.name,
                            maximum=maximum,
                        ),
                    )
    finally:
        source.dispose()
        target.dispose()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    source = parser.parse_args().source.resolve(strict=True)
    try:
        counts = migrate(source)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    except SQLAlchemyError as error:
        parser.exit(
            1,
            f"Migration did not commit ({type(error).__name__}). Check the database connection and schema.\n",
        )
    print(
        f"Copied {sum(counts.values())} records across {len(counts)} tables. Session tokens were omitted."
    )
    print(
        f"Verified {counts['academic_sessions']} timetable sessions and {counts['users']} accounts."
    )
