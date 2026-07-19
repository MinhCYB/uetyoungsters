from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CandidateProfileUpdate(BaseModel):
    profile_type: str | None = Field(default=None, pattern="^(HIGH_SCHOOL|UNIVERSITY|PROFESSIONAL)$")
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=10, le=100)
    region: str | None = Field(default=None, max_length=200)
    school: str | None = Field(default=None, max_length=240)
    grade: str | None = Field(default=None, max_length=40)
    major: str | None = Field(default=None, max_length=240)
    study_year: int | None = Field(default=None, ge=1, le=12)
    gpa: float | None = Field(default=None, ge=0, le=10)
    current_job: str | None = Field(default=None, max_length=240)
    experience_years: float | None = Field(default=None, ge=0, le=80)
    current_career_id: str | None = Field(default=None, max_length=120)
    basic_information: dict | None = None


class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    profile_type: str
    student_code: str | None
    gender: str | None
    age: int | None
    region: str | None
    school: str | None
    grade: str | None
    major: str | None
    study_year: int | None
    gpa: float | None
    current_job: str | None
    experience_years: float | None
    current_career_id: str | None
    basic_information: dict
    version: int
    updated_at: datetime


class AcademicRecordInput(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=0, le=10)
    semester: str = Field(min_length=1, max_length=40)
    conduct: str | None = Field(default=None, max_length=40)
    teacher_note: str | None = Field(default=None, max_length=2000)


class AcademicRecordResponse(AcademicRecordInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class TeacherEvaluationInput(BaseModel):
    observation: str = Field(min_length=1, max_length=4000)


class TeacherEvaluationResponse(TeacherEvaluationInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    teacher_id: str
    created_at: datetime
