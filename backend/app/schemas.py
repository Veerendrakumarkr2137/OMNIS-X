from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False
    portal: Literal["Admin", "HOD", "Faculty", "Student", "Operator"] | None = None


class Interval(BaseModel):
    day: date
    start: int = Field(ge=0, lt=1440)
    end: int = Field(gt=0, le=1440)
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def check_interval(self):
        if self.start >= self.end:
            raise ValueError("End time must follow start time.")
        return self


class AbsenceInterval(Interval):
    end_day: date | None = None

    @model_validator(mode="after")
    def check_date_range(self):
        if self.end_day is not None:
            if self.end_day < self.day:
                raise ValueError("To date must not precede from date.")
            if (self.end_day - self.day).days > 30:
                raise ValueError("Date range cannot exceed 31 days.")
        return self


class Failure(Interval):
    roots: list[str] = Field(min_length=1, max_length=12)
    title: str = Field(min_length=1, max_length=100)
    severity: Literal["Low", "Medium", "High", "Critical"] = "Medium"


class Generate(BaseModel):
    case_id: int


class Policy(BaseModel):
    allow_substitution: bool | None = None
    require_consent: bool = False
    mode: Literal["Manual", "Assisted", "Automatic"] = "Assisted"
    hod_approval: bool = False
    delay_weight: int = Field(default=1, ge=0, le=1000)
    room_weight: int = Field(default=50, ge=0, le=10000)
    faculty_weight: int = Field(default=100, ge=0, le=10000)
    travel_minutes: int = Field(default=0, ge=0, le=60)
    auto_penalty_limit: int = Field(default=50, ge=0, le=10000)


class ConsentDecision(BaseModel):
    decision: Literal["Accepted", "Declined"]
