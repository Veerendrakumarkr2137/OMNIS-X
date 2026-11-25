import base64
import csv
import io
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from .accounts import add_user
from .admin import IdentityInput, LessonInput, ProfileInput, add_lesson, save_profile
from .database import Resource
from .services import lock_state


class ImportInput(BaseModel):
    filename: str = Field(max_length=255)
    content: str = Field(max_length=1_400_000)


def spreadsheet_rows(file):
    with ZipFile(io.BytesIO(file)) as book:
        if sum(info.file_size for info in book.infolist()) > 5_000_000:
            raise ValueError("Workbook is too large.")

        def read(name):
            data = book.read(name)
            if b"<!DOCTYPE" in data.upper():
                raise ValueError("Unsupported workbook markup.")
            return ET.fromstring(data)

        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = [
                "".join(x.text or "" for x in node.findall(".//{*}t"))
                for node in read("xl/sharedStrings.xml")
            ]
        sheet = next(
            (
                name
                for name in book.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            ),
            None,
        )
        if not sheet:
            raise ValueError("No worksheet found.")
        values = []
        for row in read(sheet).findall(".//{*}sheetData/{*}row"):
            cells = []
            for cell in row.findall("{*}c"):
                column = 0
                for letter in re.match(r"[A-Z]+", cell.attrib["r"]).group():
                    column = column * 26 + ord(letter) - 64
                if column > 100:
                    raise ValueError("Use at most 100 columns.")
                cells.extend([""] * (column - len(cells)))
                raw = cell.findtext("{*}v", "")
                if cell.attrib.get("t") == "s":
                    raw = strings[int(raw)]
                elif cell.attrib.get("t") == "inlineStr":
                    raw = "".join(x.text or "" for x in cell.findall(".//{*}t"))
                cells[column - 1] = raw
            if any(cells):
                values.append(cells)
        return [dict(zip(values[0], row)) for row in values[1:]] if values else []


def import_accounts(db, actor, data, demo):
    try:
        contents = base64.b64decode(data.content, validate=True)
        filename = data.filename.lower()
        if filename.endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(contents.decode("utf-8-sig"))))
        elif filename.endswith(".xlsx"):
            records = spreadsheet_rows(contents)
        else:
            raise ValueError("Select a CSV or XLSX file.")
    except (
        ValueError,
        KeyError,
        AttributeError,
        IndexError,
        BadZipFile,
        ET.ParseError,
    ) as error:
        raise HTTPException(
            422, "Could not read the file. Check its format and size."
        ) from error
    if not 1 <= len(records) <= 500:
        raise HTTPException(422, "Provide 1–500 records.")
    state = lock_state(db)
    created = 0
    for index, raw in enumerate(records, 2):
        try:
            row = {
                key.strip().lower(): value.strip()
                for key, value in raw.items()
                if key and isinstance(value, str)
            }
            kind = row.get("record", "").lower()
            if kind == "session":
                row["needs"] = [
                    value.strip()
                    for value in row.get("needs", "").split("|")
                    if value.strip()
                ]
                add_lesson(db, actor, LessonInput.model_validate(row), state)
                created += 1
                continue
            if kind in ("department", "cohort"):
                save_profile(
                    db,
                    actor,
                    ProfileInput(
                        name=row["name"],
                        kind=kind.title(),
                        dept=row.get("dept") or None,
                        capacity=row.get("capacity") or 40,
                    ),
                    locked=True,
                )
                created += 1
                continue
            if row.get("role") == "Faculty" and not row.get("resource"):
                if not row.get("subjects"):
                    raise HTTPException(
                        422, "Provide subjects for the new faculty profile."
                    )
                resource = save_profile(
                    db,
                    actor,
                    ProfileInput(
                        name=row["name"],
                        kind="Faculty",
                        dept=row.get("dept"),
                        subjects=[
                            name.strip()
                            for name in row["subjects"].split("|")
                            if name.strip()
                        ],
                    ),
                    locked=True,
                )
                row["resource"] = resource.id
            for key in ("email", "dept", "resource"):
                if row.get(key) == "":
                    del row[key]
            if (
                row.get("role") == "Student"
                and not row.get("resource")
                and row.get("cohort")
            ):
                cohort = (
                    db.query(Resource)
                    .filter_by(kind="Cohort", name=row["cohort"], dept=row.get("dept"))
                    .one_or_none()
                )
                row["resource"] = cohort.id if cohort else None
            if "enrollments" in row and row.get("role") == "Student":
                row["enrollments"] = dict(
                    tuple(part.strip() for part in entry.rsplit(":", 1))
                    if ":" in entry
                    else (entry.strip(), "Core")
                    for entry in row["enrollments"].split("|")
                    if entry.strip()
                )
            elif "enrollments" in row:
                del row["enrollments"]
            add_user(db, actor, IdentityInput.model_validate(row), demo, locked=True)
            created += 1
        except ValidationError as error:
            issue = error.errors(include_input=False)[0]
            raise HTTPException(
                422, f"Row {index} · {issue['loc'][0]} is invalid."
            ) from error
        except KeyError as error:
            raise HTTPException(
                422, f"Row {index} · a required column is missing."
            ) from error
        except HTTPException as error:
            raise HTTPException(
                error.status_code, f"Row {index} · {error.detail}"
            ) from error
    return {"created": created}
