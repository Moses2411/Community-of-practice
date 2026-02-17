from pydantic import BaseModel, EmailStr
from datetime import datetime
from model import Ratings, Venue


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    program: str | None = None
    
class Login(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str | None
    email: EmailStr
    program: str | None

    class Config:
        from_attributes = True

class TutorCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    specialty: str
    department: str

class TutorResponse(BaseModel):
    id: int
    username: str
    email:EmailStr
    specialty: str
    department: str

    class Config:
        from_attributes = True
        
class CourseCreate(BaseModel):
    title: str
    course_code: str

class CourseResponse(BaseModel):
    id: int
    title: str
    course_code: str

    class Config:
        from_attributes = True

class ReviewCreate(BaseModel):
    tutor_id: int
    rating: str
    comment: str
    created_at: datetime

class ReviewResponse(BaseModel):
    id: int
    tutor_id: int
    student_mail:str
    student_id: int
    rating: str
    comment:str
    created_at: datetime

    class Config:
        from_attributes = True

class CreatePoll(BaseModel):
    course_id: int
    tutor_id: int
    day: str
    time: str
    venue: Venue

class PollResponse(BaseModel):
    id: int
    course_id: int
    tutor_id: int
    day:str
    time:str
    venue: Venue

class VoteCreate(BaseModel):
    poll_id: int

class VoteResponse(BaseModel):
    id: int
    poll_id: int
    student_id: int
    
    class Config:
        from_attributes = True

# Add to schemas.py
class SchedulePreferenceCreate(BaseModel):
    course_id: int
    tutor_id: int
    preferred_day: str
    preferred_time: str
    preferred_venue: str

class SchedulePreferenceResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    tutor_id: int
    preferred_day: str
    preferred_time: str
    preferred_venue: str
    submitted_at: datetime
    
    class Config:
        from_attributes = True

class TutorialScheduleResponse(BaseModel):
    id: int
    course_id: int
    tutor_id: int
    scheduled_day: str
    scheduled_time: str
    scheduled_venue: str
    total_votes: int
    is_finalized: bool
    finalized_at: datetime | None
    
    class Config:
        from_attributes = True

class CourseScheduleAggregation(BaseModel):
    course_id: int
    tutor_selections: dict[int, int]  # tutor_id: count
    day_selections: dict[str, int]     # day: count
    time_selections: dict[str, int]    # time: count
    venue_selections: dict[str, int]   # venue: count
    total_preferences: int