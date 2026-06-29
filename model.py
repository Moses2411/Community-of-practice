from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


def utcnow():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(String(40), unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), default="student", nullable=False)
    study_group = Column(String(30), default="experimental", nullable=False)
    programme = Column(String(120), default="Computer Science Education")
    department = Column(String(120), default="Computer Science")
    level = Column(String(30), nullable=True)
    interests = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_login_at = Column(DateTime, nullable=True)
    security_question = Column(String(255), nullable=True)
    security_answer_hash = Column(String(255), nullable=True)

    consent_records = relationship("ConsentRecord", back_populates="user", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    resource_views = relationship("ResourceView", back_populates="user", cascade="all, delete-orphan")
    resource_feedback = relationship("ResourceFeedback", back_populates="user", cascade="all, delete-orphan")
    threads = relationship("DiscussionThread", back_populates="author", cascade="all, delete-orphan")
    replies = relationship("DiscussionReply", back_populates="author", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")
    practical_attempts = relationship("PracticalAttempt", back_populates="user", cascade="all, delete-orphan")
    reflections = relationship("Reflection", back_populates="user", cascade="all, delete-orphan")
    platform_feedback = relationship("PlatformFeedback", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    academic_records = relationship("AcademicRecord", back_populates="user", cascade="all, delete-orphan")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consent_version = Column(String(40), default="v1")
    agreed = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    agreed_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="consent_records")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(8), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(160), unique=True, nullable=False)
    code = Column(String(40), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    facilitator = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    memberships = relationship("Membership", back_populates="course", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="course", cascade="all, delete-orphan")
    threads = relationship("DiscussionThread", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")
    practical_exercises = relationship("PracticalExercise", back_populates="course", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    learning_goal = Column(Text, nullable=True)
    joined_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="memberships")
    course = relationship("Course", back_populates="memberships")

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="unique_user_course_membership"),)


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(180), nullable=False)
    resource_type = Column(String(40), default="note", nullable=False)
    difficulty = Column(String(40), default="beginner", nullable=False)
    estimated_minutes = Column(Integer, default=15)
    url = Column(String(500), nullable=True)
    video_url = Column(Text, nullable=True)
    blog_url = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    course = relationship("Course", back_populates="resources")
    created_by = relationship("User")
    views = relationship("ResourceView", back_populates="resource", cascade="all, delete-orphan")
    feedback = relationship("ResourceFeedback", back_populates="resource", cascade="all, delete-orphan")


class ResourceView(Base):
    __tablename__ = "resource_views"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seconds_spent = Column(Integer, default=0)
    viewed_at = Column(DateTime, default=utcnow)

    resource = relationship("Resource", back_populates="views")
    user = relationship("User", back_populates="resource_views")


class ResourceFeedback(Base):
    __tablename__ = "resource_feedback"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    usefulness_rating = Column(Integer, nullable=False)
    clarity_rating = Column(Integer, nullable=False)
    confidence_after = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    resource = relationship("Resource", back_populates="feedback")
    user = relationship("User", back_populates="resource_feedback")


class DiscussionThread(Base):
    __tablename__ = "discussion_threads"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(String(240), nullable=True)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    course = relationship("Course", back_populates="threads")
    author = relationship("User", back_populates="threads")
    replies = relationship("DiscussionReply", back_populates="thread", cascade="all, delete-orphan")


class DiscussionReply(Base):
    __tablename__ = "discussion_replies"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("discussion_threads.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    helpful_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    thread = relationship("DiscussionThread", back_populates="replies")
    author = relationship("User", back_populates="replies")
    helpful_votes = relationship("ReplyHelpfulVote", back_populates="reply", cascade="all, delete-orphan")


class ReplyHelpfulVote(Base):
    __tablename__ = "reply_helpful_votes"

    id = Column(Integer, primary_key=True, index=True)
    reply_id = Column(Integer, ForeignKey("discussion_replies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    reply = relationship("DiscussionReply", back_populates="helpful_votes")
    user = relationship("User")

    __table_args__ = (UniqueConstraint("reply_id", "user_id", name="unique_reply_helpful_vote"),)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(180), nullable=False)
    quiz_type = Column(String(40), default="test", nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    course = relationship("Course", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(Text, nullable=False)
    question_type = Column(String(10), default="mcq", nullable=False)  # "mcq" or "theory"
    option_a = Column(String(300), nullable=False)
    option_b = Column(String(300), nullable=False)
    option_c = Column(String(300), nullable=False)
    option_d = Column(String(300), nullable=False)
    correct_option = Column(String(1), nullable=True)
    explanation = Column(Text, nullable=True)
    points = Column(Integer, default=1)

    quiz = relationship("Quiz", back_populates="questions")
    answers = relationship("QuizAnswer", back_populates="question", cascade="all, delete-orphan")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, default=0)
    total_points = Column(Float, default=0)
    seconds_spent = Column(Integer, default=0)
    started_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, default=utcnow)

    quiz = relationship("Quiz", back_populates="attempts")
    user = relationship("User", back_populates="quiz_attempts")
    answers = relationship("QuizAnswer", back_populates="attempt", cascade="all, delete-orphan")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False)
    selected_option = Column(String(1), nullable=True)
    answer_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False)
    points_awarded = Column(Float, default=0)
    answered_at = Column(DateTime, default=utcnow)

    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("QuizQuestion", back_populates="answers")


class PracticalExercise(Base):
    __tablename__ = "practical_exercises"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(180), nullable=False)
    practical_type = Column(String(40), nullable=False)  # "python", "java", or "database"
    difficulty = Column(String(40), default="beginner", nullable=False)
    prompt = Column(Text, nullable=False)
    starter_code = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=True)
    solution_notes = Column(Text, nullable=True)
    checks_json = Column(Text, nullable=True)
    release_key = Column(String(40), nullable=True, index=True)
    release_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    source = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    course = relationship("Course", back_populates="practical_exercises")
    attempts = relationship("PracticalAttempt", back_populates="exercise", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "ix_practical_exercises_release_unique",
            "course_id",
            "release_key",
            "practical_type",
            "title",
            unique=True,
        ),
    )


class PracticalAttempt(Base):
    __tablename__ = "practical_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("practical_exercises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    submitted_code = Column(Text, nullable=False)
    score = Column(Float, default=0)
    total_points = Column(Float, default=100)
    feedback_json = Column(Text, nullable=True)
    completed_at = Column(DateTime, default=utcnow)

    exercise = relationship("PracticalExercise", back_populates="attempts")
    user = relationship("User", back_populates="practical_attempts")


class Reflection(Base):
    __tablename__ = "reflections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_label = Column(String(80), nullable=False)
    learned = Column(Text, nullable=False)
    challenge = Column(Text, nullable=True)
    community_help = Column(Text, nullable=True)
    confidence_rating = Column(Integer, nullable=False)
    engagement_rating = Column(Integer, nullable=False)
    suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="reflections")


class PlatformFeedback(Base):
    __tablename__ = "platform_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(80), default="general", nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="platform_feedback")


class AcademicRecord(Base):
    __tablename__ = "academic_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assessment_name = Column(String(160), nullable=False)
    assessment_type = Column(String(60), default="external", nullable=False)
    score = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="academic_records")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(80), nullable=False)
    entity_type = Column(String(80), nullable=True)
    entity_id = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="activity_logs")


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    survey_type = Column(String(40), nullable=False)  # "presurvey" or "postsurvey"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    questions = relationship("SurveyQuestion", back_populates="survey", cascade="all, delete-orphan")
    responses = relationship("SurveyResponse", back_populates="survey", cascade="all, delete-orphan")


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(Text, nullable=False)
    dimension = Column(String(60), nullable=True)  # e.g., "self_efficacy", "attitude", "tech_acceptance"
    order_index = Column(Integer, default=0)

    survey = relationship("Survey", back_populates="questions")
    answers = relationship("SurveyAnswer", back_populates="question", cascade="all, delete-orphan")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime, default=utcnow)

    survey = relationship("Survey", back_populates="responses")
    user = relationship("User")
    answers = relationship("SurveyAnswer", back_populates="response", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("survey_responses.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("survey_questions.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)  # Likert scale 1-5

    response = relationship("SurveyResponse", back_populates="answers")
    question = relationship("SurveyQuestion", back_populates="answers")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    attachment_url = Column(String, nullable=True)
    attachment_name = Column(String, nullable=True)
    attachment_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    course = relationship("Course")
    author = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    kind = Column(String(60), default="general")  # "reply", "helpful", "resolved", "system"
    entity_type = Column(String(80), nullable=True)
    entity_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
