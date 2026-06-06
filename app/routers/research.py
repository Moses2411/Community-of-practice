from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.dependencies import ResearcherUser, SessionDep
from app.serializers import serialize_user
from app.utils import csv_response, log_activity
from model import (
    AcademicRecord,
    ActivityLog,
    Course,
    DiscussionReply,
    DiscussionThread,
    PlatformFeedback,
    QuizAttempt,
    Reflection,
    ResourceFeedback,
    ResourceView,
    User,
)
from model import Resource as ResourceModel

router = APIRouter()


@router.get("/api/research/users")
def research_users(db: SessionDep, current_user: ResearcherUser):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [serialize_user(user) for user in users]


@router.get("/api/research/dashboard")
def research_dashboard(db: SessionDep, current_user: ResearcherUser):
    users = db.scalar(select(func.count(User.id))) or 0
    experimental_users = db.scalar(select(func.count(User.id)).where(User.study_group == "experimental")) or 0
    control_users = db.scalar(select(func.count(User.id)).where(User.study_group == "control")) or 0
    quiz_average = db.scalar(
        select(func.avg((QuizAttempt.score * 100.0) / QuizAttempt.total_points)).where(QuizAttempt.total_points > 0)
    )
    engagement_average = db.scalar(select(func.avg(Reflection.engagement_rating)))

    return {
        "users": users,
        "experimental_users": experimental_users,
        "control_users": control_users,
        "courses": db.scalar(select(func.count(Course.id))) or 0,
        "resources": db.scalar(select(func.count(ResourceModel.id))) or 0,
        "discussions": db.scalar(select(func.count(DiscussionThread.id))) or 0,
        "replies": db.scalar(select(func.count(DiscussionReply.id))) or 0,
        "quiz_attempts": db.scalar(select(func.count(QuizAttempt.id))) or 0,
        "reflections": db.scalar(select(func.count(Reflection.id))) or 0,
        "feedback_items": (db.scalar(select(func.count(PlatformFeedback.id))) or 0)
        + (db.scalar(select(func.count(ResourceFeedback.id))) or 0),
        "average_quiz_percentage": round(float(quiz_average or 0), 2),
        "average_engagement_rating": round(float(engagement_average or 0), 2),
        "activity_events": db.scalar(select(func.count(ActivityLog.id))) or 0,
    }


def export_users(db) -> tuple[list[str], list[list]]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return (
        ["research_id", "study_group", "role", "programme", "department", "level", "interests", "created_at"],
        [
            [
                user.research_id,
                user.study_group,
                user.role,
                user.programme,
                user.department,
                user.level,
                user.interests,
                user.created_at,
            ]
            for user in users
        ],
    )


def export_activity(db) -> tuple[list[str], list[list]]:
    logs = db.scalars(select(ActivityLog).order_by(ActivityLog.created_at)).all()
    return (
        ["event_id", "research_id", "action", "entity_type", "entity_id", "metadata", "created_at"],
        [
            [
                log.id,
                log.user.research_id if log.user else None,
                log.action,
                log.entity_type,
                log.entity_id,
                log.metadata_json,
                log.created_at,
            ]
            for log in logs
        ],
    )


def export_quiz_attempts(db) -> tuple[list[str], list[list]]:
    attempts = db.scalars(select(QuizAttempt).order_by(QuizAttempt.completed_at)).all()
    return (
        [
            "attempt_id", "research_id", "study_group", "topic_code", "quiz_title",
            "quiz_type", "score", "total_points", "percentage", "seconds_spent", "completed_at",
        ],
        [
            [
                attempt.id,
                attempt.user.research_id,
                attempt.user.study_group,
                attempt.quiz.topic.code,
                attempt.quiz.title,
                attempt.quiz.quiz_type,
                attempt.score,
                attempt.total_points,
                round((attempt.score / attempt.total_points * 100) if attempt.total_points else 0, 2),
                attempt.seconds_spent,
                attempt.completed_at,
            ]
            for attempt in attempts
        ],
    )


def export_feedback(db) -> tuple[list[str], list[list]]:
    rows = []
    for feedback in db.scalars(select(ResourceFeedback).order_by(ResourceFeedback.created_at)).all():
        rows.append(
            [
                "resource", feedback.id, feedback.user.research_id, feedback.resource.title,
                feedback.usefulness_rating, feedback.clarity_rating, feedback.confidence_after,
                feedback.comment, feedback.created_at,
            ]
        )
    for feedback in db.scalars(select(PlatformFeedback).order_by(PlatformFeedback.created_at)).all():
        rows.append(
            [
                "platform", feedback.id, feedback.user.research_id, feedback.category,
                feedback.rating, None, None, feedback.comment, feedback.created_at,
            ]
        )
    return (
        ["feedback_type", "feedback_id", "research_id", "target_or_category",
         "rating_or_usefulness", "clarity_rating", "confidence_after", "comment", "created_at"],
        rows,
    )


def export_reflections(db) -> tuple[list[str], list[list]]:
    reflections = db.scalars(select(Reflection).order_by(Reflection.created_at)).all()
    return (
        ["reflection_id", "research_id", "study_group", "week_label", "confidence_rating",
         "engagement_rating", "learned", "challenge", "community_help", "suggestions", "created_at"],
        [
            [
                reflection.id, reflection.user.research_id, reflection.user.study_group,
                reflection.week_label, reflection.confidence_rating, reflection.engagement_rating,
                reflection.learned, reflection.challenge, reflection.community_help,
                reflection.suggestions, reflection.created_at,
            ]
            for reflection in reflections
        ],
    )


def export_discussions(db) -> tuple[list[str], list[list]]:
    rows = []
    for thread in db.scalars(select(DiscussionThread).order_by(DiscussionThread.created_at)).all():
        rows.append(
            [
                "thread", thread.id, thread.author.research_id, thread.topic.code,
                thread.title, thread.body, thread.tags, thread.is_resolved,
                len(thread.replies), thread.created_at,
            ]
        )
    for reply in db.scalars(select(DiscussionReply).order_by(DiscussionReply.created_at)).all():
        rows.append(
            [
                "reply", reply.id, reply.author.research_id, reply.thread.topic.code,
                reply.thread.title, reply.body, None, None, reply.helpful_count, reply.created_at,
            ]
        )
    return (
        ["item_type", "item_id", "research_id", "topic_code", "thread_title", "text",
         "tags", "is_resolved", "reply_or_helpful_count", "created_at"],
        rows,
    )


def export_academic_records(db) -> tuple[list[str], list[list]]:
    records = db.scalars(select(AcademicRecord).order_by(AcademicRecord.recorded_at)).all()
    return (
        ["record_id", "research_id", "study_group", "assessment_name", "assessment_type",
         "score", "total", "percentage", "notes", "recorded_at"],
        [
            [
                record.id, record.user.research_id, record.user.study_group,
                record.assessment_name, record.assessment_type, record.score, record.total,
                round((record.score / record.total * 100) if record.total else 0, 2),
                record.notes, record.recorded_at,
            ]
            for record in records
        ],
    )


def export_combined(db) -> tuple[list[str], list[list]]:
    rows = []
    users = db.scalars(select(User).order_by(User.research_id)).all()
    for user in users:
        attempts = user.quiz_attempts
        pretest_scores = [
            (a.score / a.total_points * 100) for a in attempts
            if a.total_points and a.quiz.quiz_type == "pretest"
        ]
        posttest_scores = [
            (a.score / a.total_points * 100) for a in attempts
            if a.total_points and a.quiz.quiz_type == "posttest"
        ]
        practice_scores = [
            (a.score / a.total_points * 100) for a in attempts
            if a.total_points and a.quiz.quiz_type == "practice"
        ]
        logs = user.activity_logs
        reflections = user.reflections
        academic = user.academic_records
        rows.append(
            [
                user.research_id, user.study_group, user.level,
                len(logs), len(user.memberships), len(user.resource_views),
                len(user.threads), len(user.replies), len(attempts),
                round(sum(pretest_scores) / len(pretest_scores), 2) if pretest_scores else None,
                round(sum(practice_scores) / len(practice_scores), 2) if practice_scores else None,
                round(sum(posttest_scores) / len(posttest_scores), 2) if posttest_scores else None,
                round(sum(r.engagement_rating for r in reflections) / len(reflections), 2) if reflections else None,
                round(sum(r.confidence_rating for r in reflections) / len(reflections), 2) if reflections else None,
                round(
                    sum(rec.score / rec.total * 100 for rec in academic if rec.total)
                    / len([rec for rec in academic if rec.total]), 2
                ) if academic else None,
            ]
        )
    return (
        ["research_id", "study_group", "level", "activity_event_count", "topic_memberships",
         "resource_views", "discussion_threads", "discussion_replies", "quiz_attempts",
         "pretest_avg_percent", "practice_avg_percent", "posttest_avg_percent",
         "reflection_engagement_avg", "reflection_confidence_avg", "external_academic_avg_percent"],
        rows,
    )


EXPORTERS = {
    "users": export_users,
    "activity": export_activity,
    "quiz_attempts": export_quiz_attempts,
    "feedback": export_feedback,
    "reflections": export_reflections,
    "discussions": export_discussions,
    "academic_records": export_academic_records,
    "combined": export_combined,
}


@router.get("/api/research/export/{dataset}")
def export_dataset(dataset: str, db: SessionDep, current_user: ResearcherUser):
    exporter = EXPORTERS.get(dataset)
    if exporter is None:
        available = ", ".join(sorted(EXPORTERS))
        raise HTTPException(status_code=404, detail=f"Unknown dataset. Available datasets: {available}.")
    headers, rows = exporter(db)
    return csv_response(f"{dataset}.csv", headers, rows)
