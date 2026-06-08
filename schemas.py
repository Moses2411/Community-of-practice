from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Role = Literal["student", "facilitator", "researcher", "admin"]
StudyGroup = Literal["experimental", "control"]
QuizType = Literal["pretest", "practice", "posttest"]


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    programme: str = "Computer Science Education"
    department: str = "Computer Science"
    level: str | None = None
    interests: str | None = None
    study_group: StudyGroup = "experimental"
    accepted_research_consent: bool = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    research_id: str
    full_name: str
    email: EmailStr
    role: str
    study_group: str
    programme: str | None
    department: str | None
    level: str | None
    interests: str | None
    created_at: datetime


class ConsentCreate(BaseModel):
    agreed: bool = True
    consent_version: str = "v1"
    notes: str | None = None


class CourseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    description: str | None = None
    facilitator: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    code: str
    description: str | None
    facilitator: str | None
    created_at: datetime
    member_count: int = 0
    resource_count: int = 0
    discussion_count: int = 0


class MembershipCreate(BaseModel):
    learning_goal: str | None = None


class ResourceCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=3, max_length=180)
    resource_type: str = "note"
    difficulty: str = "beginner"
    estimated_minutes: int = Field(default=15, ge=1, le=300)
    url: str | None = None
    video_url: str | None = None
    blog_url: str | None = None
    body: str | None = None


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    resource_type: str
    difficulty: str
    estimated_minutes: int
    url: str | None
    video_url: str | None
    blog_url: str | None
    body: str | None
    created_at: datetime
    average_usefulness: float | None = None
    view_count: int = 0


class ResourceFeedbackCreate(BaseModel):
    usefulness_rating: int = Field(ge=1, le=5)
    clarity_rating: int = Field(ge=1, le=5)
    confidence_after: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None


class DiscussionThreadCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3)
    tags: str | None = None


class DiscussionReplyCreate(BaseModel):
    body: str = Field(min_length=2)


class ReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    author_id: int
    author_name: str | None = None
    body: str
    helpful_count: int
    created_at: datetime


class DiscussionThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    author_id: int
    author_name: str | None = None
    title: str
    body: str
    tags: str | None
    is_resolved: bool
    created_at: datetime
    reply_count: int = 0
    replies: list[ReplyOut] = []


class QuizCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=3, max_length=180)
    quiz_type: QuizType = "practice"
    description: str | None = None


class QuizQuestionCreate(BaseModel):
    prompt: str = Field(min_length=3)
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: Literal["a", "b", "c", "d"]
    explanation: str | None = None
    points: int = Field(default=1, ge=1, le=20)


class QuizQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    points: int
    explanation: str | None = None
    correct_option: str | None = None


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    quiz_type: str
    description: str | None
    created_at: datetime
    question_count: int = 0
    questions: list[QuizQuestionOut] = []


class QuizAnswerSubmit(BaseModel):
    question_id: int
    selected_option: Literal["a", "b", "c", "d"] | None = None


class QuizSubmit(BaseModel):
    seconds_spent: int = Field(default=0, ge=0)
    answers: list[QuizAnswerSubmit]


class QuizAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    user_id: int
    score: float
    total_points: float
    percentage: float
    seconds_spent: int
    completed_at: datetime


class ReflectionCreate(BaseModel):
    week_label: str = Field(min_length=2, max_length=80)
    learned: str = Field(min_length=3)
    challenge: str | None = None
    community_help: str | None = None
    confidence_rating: int = Field(ge=1, le=5)
    engagement_rating: int = Field(ge=1, le=5)
    suggestions: str | None = None


class ReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    week_label: str
    learned: str
    challenge: str | None
    community_help: str | None
    confidence_rating: int
    engagement_rating: int
    suggestions: str | None
    created_at: datetime


class PlatformFeedbackCreate(BaseModel):
    category: str = "general"
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class AcademicRecordCreate(BaseModel):
    user_id: int
    assessment_name: str = Field(min_length=2, max_length=160)
    assessment_type: str = "external"
    score: float = Field(ge=0)
    total: float = Field(gt=0)
    notes: str | None = None


class ActivityCreate(BaseModel):
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    metadata: dict | None = None


class DashboardOut(BaseModel):
    users: int
    experimental_users: int
    control_users: int
    courses: int
    resources: int
    discussions: int
    replies: int
    quiz_attempts: int
    reflections: int
    feedback_items: int
    average_quiz_percentage: float
    average_engagement_rating: float
    activity_events: int


# ---- Survey schemas ----
class SurveyAnswerSubmit(BaseModel):
    question_id: int
    rating: int = Field(ge=1, le=5)


class SurveySubmit(BaseModel):
    answers: list[SurveyAnswerSubmit]


class SurveyQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt: str
    dimension: str | None = None
    order_index: int = 0


class SurveyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    survey_type: str
    description: str | None
    is_active: bool
    question_count: int = 0
    questions: list[SurveyQuestionOut] = []


class SurveyResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    survey_id: int
    user_id: int
    completed_at: datetime
    dimension_scores: dict | None = None
