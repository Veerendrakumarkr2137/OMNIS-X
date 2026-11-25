"""Emit the initial private PostgreSQL schema from the OMNIS-X models."""

import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import Base, POSTGRES_SCHEMA


def schema_sql():
    schema = POSTGRES_SCHEMA
    statements = [
        f"CREATE SCHEMA {schema}",
        "CREATE ROLE omnisx_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
        f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC, anon, authenticated, service_role",
        f"GRANT USAGE ON SCHEMA {schema} TO omnisx_app",
    ]
    dialect = postgresql.dialect()
    options = dict(
        dialect=dialect,
        schema_translate_map={None: schema},
        render_schema_translate=True,
    )
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(**options)).strip())
        for index in sorted(table.indexes, key=lambda item: item.name):
            statements.append(str(CreateIndex(index).compile(**options)))
        qualified = f"{schema}.{table.name}"
        statements.extend(
            [
                f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY",
                f"CREATE POLICY backend_access ON {qualified} TO omnisx_app USING (true) WITH CHECK (true)",
            ]
        )
    statements.extend(
        [
            f"CREATE INDEX ix_users_lower_login_id ON {schema}.users (lower(id))",
            f"CREATE INDEX ix_users_department_role ON {schema}.users (dept, role)",
            f"CREATE INDEX ix_lessons_department_day ON {schema}.academic_sessions (dept, day)",
            f"CREATE INDEX ix_lessons_faculty_day ON {schema}.academic_sessions (faculty, day)",
            f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {schema} TO omnisx_app",
            f"GRANT DELETE ON {schema}.auth_sessions, {schema}.student_enrollments TO omnisx_app",
            f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {schema} TO omnisx_app",
        ]
    )
    return ";\n\n".join(statements) + ";\n"


if __name__ == "__main__":
    print(schema_sql(), end="")
