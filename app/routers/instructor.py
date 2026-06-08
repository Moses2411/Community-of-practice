from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.dependencies import ContentManagerUser, SessionDep
from model import (
    Course,
    DiscussionReply,
    DiscussionThread,
    Membership,
    QuizAttempt,
    ResourceView,
    User,
)

router = APIRouter()


@router.get("/api/instructor/courses")
def list_instructor_courses(db: SessionDep, current_user: ContentManagerUser):
    courses = db.scalars(select(Course).order_by(Course.title)).all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "title": c.title,
            "member_count": len(c.memberships),
            "resource_count": len(c.resources),
            "quiz_count": len(c.quizzes),
            "discussion_count": len(c.threads),
        }
        for c in courses
    ]


@router.get("/api/instructor/courses/{course_id}/stats")
def instructor_course_stats(course_id: int, db: SessionDep, current_user: ContentManagerUser):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    member_ids = [m.user_id for m in course.memberships]
    member_count = len(member_ids)

    experimental_count = 0
    control_count = 0
    for m in course.memberships:
        if m.user.study_group == "experimental":
            experimental_count += 1
        elif m.user.study_group == "control":
            control_count += 1

    quiz_attempts = db.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.quiz.has(course_id=course_id)
        )
    ) or 0 if member_ids else 0

    quiz_avg = db.scalar(
        select(func.avg(QuizAttempt.score / QuizAttempt.total_points * 100)).where(
            QuizAttempt.quiz.has(course_id=course_id),
            QuizAttempt.total_points > 0,
        )
    )
    quiz_average = round(quiz_avg, 1) if quiz_avg else None

    thread_count = len(course.threads)
    reply_count = db.scalar(
        select(func.count(DiscussionReply.id)).where(
            DiscussionReply.thread.has(course_id=course_id)
        )
    ) or 0

    resource_view_count = db.scalar(
        select(func.count(ResourceView.id)).where(
            ResourceView.resource.has(course_id=course_id)
        )
    ) or 0

    quiz_type_avgs = {}
    for quiz in course.quizzes:
        avg = db.scalar(
            select(func.avg(QuizAttempt.score / QuizAttempt.total_points * 100)).where(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.total_points > 0,
            )
        )
        if avg:
            quiz_type_avgs[quiz.quiz_type] = quiz_type_avgs.get(quiz.quiz_type, []) + [round(avg, 1)]

    quiz_breakdown = {k: round(sum(v) / len(v), 1) for k, v in quiz_type_avgs.items()}

    recent_attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.quiz.has(course_id=course_id))
        .order_by(QuizAttempt.completed_at.desc())
        .limit(10)
    ).all()

    return {
        "course_id": course_id,
        "course_title": course.title,
        "course_code": course.code,
        "member_count": member_count,
        "experimental_count": experimental_count,
        "control_count": control_count,
        "quiz_attempts": quiz_attempts,
        "quiz_average_percentage": quiz_average,
        "quiz_breakdown": quiz_breakdown,
        "thread_count": thread_count,
        "reply_count": reply_count,
        "resource_view_count": resource_view_count,
        "recent_attempts": [
            {
                "id": a.id,
                "user_name": a.user.full_name,
                "research_id": a.user.research_id,
                "study_group": a.user.study_group,
                "quiz_title": a.quiz.title,
                "quiz_type": a.quiz.quiz_type,
                "score": a.score,
                "total_points": a.total_points,
                "percentage": round(a.score / a.total_points * 100, 2) if a.total_points else 0,
                "completed_at": a.completed_at,
            }
            for a in recent_attempts
        ],
    }
