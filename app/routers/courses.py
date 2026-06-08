from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.dependencies import ContentManagerUser, CurrentUser, OptionalUser, SessionDep
from app.serializers import serialize_course
from app.utils import log_activity
from model import Course, DiscussionReply, DiscussionThread, Membership, QuizAttempt, ResourceView
from schemas import CourseCreate, MembershipCreate

router = APIRouter()


@router.get("/api/courses")
def list_courses(db: SessionDep, current_user: OptionalUser):
    courses = db.scalars(select(Course).order_by(Course.title)).all()
    uid = current_user.id if current_user else None
    return [serialize_course(course, user_id=uid) for course in courses]


@router.get("/api/courses/my")
def my_courses(db: SessionDep, current_user: CurrentUser):
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == current_user.id)
    ).all()
    return [serialize_course(m.course, user_id=current_user.id) for m in memberships]


@router.post("/api/courses")
def create_course(payload: CourseCreate, db: SessionDep, current_user: ContentManagerUser):
    course = Course(
        title=payload.title.strip(),
        code=payload.code.strip().upper(),
        description=payload.description,
        facilitator=payload.facilitator,
    )
    db.add(course)
    try:
        db.flush()
        log_activity(db, current_user, "course_created", "course", course.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this title or code already exists.") from exc
    db.refresh(course)
    return serialize_course(course)


@router.post("/api/courses/{course_id}/join")
def join_course(course_id: int, payload: MembershipCreate, db: SessionDep, current_user: CurrentUser):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    existing = db.scalar(
        select(Membership).where(Membership.course_id == course_id, Membership.user_id == current_user.id)
    )
    if existing:
        return {"message": "Already joined this course.", "course": serialize_course(course, user_id=current_user.id)}

    membership = Membership(user_id=current_user.id, course_id=course_id, learning_goal=payload.learning_goal)
    db.add(membership)
    log_activity(db, current_user, "course_joined", "course", course_id, {"learning_goal": payload.learning_goal})
    db.commit()
    db.refresh(course)
    return {"message": "Course joined.", "course": serialize_course(course, user_id=current_user.id)}


@router.get("/api/courses/{course_id}/progress")
def course_progress(course_id: int, db: SessionDep, current_user: CurrentUser):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == current_user.id, Membership.course_id == course_id
        )
    )
    if membership is None and current_user.role not in {"facilitator", "researcher", "admin"}:
        raise HTTPException(status_code=403, detail="You must join this course first.")

    resource_view_count = db.scalar(
        select(func.count(ResourceView.id)).where(
            ResourceView.user_id == current_user.id,
            ResourceView.resource.has(course_id=course_id),
        )
    ) or 0

    quiz_attempt_count = db.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.quiz.has(course_id=course_id),
        )
    ) or 0

    quiz_count = len(course.quizzes)

    quiz_avg = db.scalar(
        select(func.avg(QuizAttempt.score / QuizAttempt.total_points * 100)).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.quiz.has(course_id=course_id),
            QuizAttempt.total_points > 0,
        )
    )
    quiz_average = round(quiz_avg, 1) if quiz_avg else None

    thread_count = db.scalar(
        select(func.count(DiscussionThread.id)).where(
            DiscussionThread.author_id == current_user.id,
            DiscussionThread.course_id == course_id,
        )
    ) or 0

    reply_count = db.scalar(
        select(func.count(DiscussionReply.id)).where(
            DiscussionReply.author_id == current_user.id,
            DiscussionReply.thread.has(course_id=course_id),
        )
    ) or 0

    discussion_participation = thread_count + reply_count

    return {
        "course_id": course_id,
        "resources_viewed": resource_view_count,
        "resource_count": resource_count,
        "quizzes_taken": quiz_attempt_count,
        "quiz_count": quiz_count,
        "quiz_average_percentage": quiz_average,
        "discussions_participated": discussion_participation,
        "joined_at": membership.joined_at if membership else None,
    }
