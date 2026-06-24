from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import ContentManagerUser, CurrentUser, OptionalUser, SessionDep
from app.practical_schedule import ensure_daily_practicals
from app.serializers import serialize_course
from app.utils import log_activity
from model import (
    Course,
    DiscussionReply,
    DiscussionThread,
    Membership,
    PracticalAttempt,
    PracticalExercise,
    Quiz,
    QuizAttempt,
    ResourceView,
    Resource,
)
from schemas import CourseCreate, MembershipCreate

router = APIRouter()


@router.get("/api/courses")
def list_courses(db: SessionDep, current_user: OptionalUser):
    courses = db.scalars(
        select(Course)
        .options(
            selectinload(Course.memberships),
            selectinload(Course.resources),
            selectinload(Course.threads),
        )
        .order_by(Course.title)
    ).all()
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
        raise HTTPException(status_code=409, detail="You have already joined this course.")

    if not payload.learning_goal or not payload.learning_goal.strip():
        raise HTTPException(status_code=400, detail="Please enter a learning goal before joining.")

    membership = Membership(user_id=current_user.id, course_id=course_id, learning_goal=payload.learning_goal.strip())
    db.add(membership)
    log_activity(db, current_user, "course_joined", "course", course_id, {"learning_goal": payload.learning_goal})
    db.commit()
    db.refresh(course)
    return {"message": "Course joined.", "course": serialize_course(course, user_id=current_user.id)}


@router.put("/api/courses/{course_id}/goal")
def update_learning_goal(course_id: int, payload: MembershipCreate, db: SessionDep, current_user: CurrentUser):
    membership = db.scalar(
        select(Membership).where(Membership.course_id == course_id, Membership.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="You have not joined this course.")
    if not payload.learning_goal or not payload.learning_goal.strip():
        raise HTTPException(status_code=400, detail="Learning goal cannot be empty.")
    membership.learning_goal = payload.learning_goal.strip()
    log_activity(db, current_user, "goal_updated", "course", course_id, {"learning_goal": payload.learning_goal})
    db.commit()
    return {"message": "Learning goal saved."}


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

    release = ensure_daily_practicals(db, [course_id])

    resource_view_count = db.scalar(
        select(func.count(ResourceView.id)).where(
            ResourceView.user_id == current_user.id,
            ResourceView.resource.has(course_id=course_id),
        )
    ) or 0

    resource_count = len(course.resources)

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

    practical_attempt_count = db.scalar(
        select(func.count(func.distinct(PracticalAttempt.exercise_id)))
        .join(PracticalExercise, PracticalAttempt.exercise_id == PracticalExercise.id)
        .where(
            PracticalAttempt.user_id == current_user.id,
            PracticalExercise.course_id == course_id,
            PracticalExercise.release_key == release.key,
        )
    ) or 0

    practical_count = db.scalar(
        select(func.count(PracticalExercise.id)).where(
            PracticalExercise.course_id == course_id,
            PracticalExercise.release_key == release.key,
        )
    ) or 0

    practical_avg = db.scalar(
        select(func.avg(PracticalAttempt.score / PracticalAttempt.total_points * 100)).where(
            PracticalAttempt.user_id == current_user.id,
            PracticalAttempt.exercise.has(course_id=course_id),
            PracticalAttempt.total_points > 0,
        )
    )
    practical_average = round(practical_avg, 1) if practical_avg else None

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
        "practicals_completed": practical_attempt_count,
        "practical_count": practical_count,
        "practical_average_percentage": practical_average,
        "discussions_participated": discussion_participation,
        "joined_at": membership.joined_at if membership else None,
    }


@router.get("/api/courses/progress")
def bulk_course_progress(db: SessionDep, current_user: CurrentUser):
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == current_user.id)
    ).all()
    if not memberships:
        return {}

    course_ids = [m.course_id for m in memberships]
    release = ensure_daily_practicals(db, course_ids)

    resource_views = dict(
        db.execute(
            select(Resource.course_id, func.count(ResourceView.id))
            .join(ResourceView, ResourceView.resource_id == Resource.id)
            .where(ResourceView.user_id == current_user.id, Resource.course_id.in_(course_ids))
            .group_by(Resource.course_id)
        ).all()
    )

    quiz_attempts = dict(
        db.execute(
            select(Quiz.course_id, func.count(QuizAttempt.id))
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == current_user.id, Quiz.course_id.in_(course_ids))
            .group_by(Quiz.course_id)
        ).all()
    )

    quiz_avgs = dict(
        db.execute(
            select(Quiz.course_id, func.avg(QuizAttempt.score / QuizAttempt.total_points * 100))
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == current_user.id, Quiz.course_id.in_(course_ids), QuizAttempt.total_points > 0)
            .group_by(Quiz.course_id)
        ).all()
    )

    practical_attempts = dict(
        db.execute(
            select(PracticalExercise.course_id, func.count(func.distinct(PracticalAttempt.exercise_id)))
            .join(PracticalAttempt, PracticalAttempt.exercise_id == PracticalExercise.id)
            .where(
                PracticalAttempt.user_id == current_user.id,
                PracticalExercise.course_id.in_(course_ids),
                PracticalExercise.release_key == release.key,
            )
            .group_by(PracticalExercise.course_id)
        ).all()
    )

    practical_counts = dict(
        db.execute(
            select(PracticalExercise.course_id, func.count(PracticalExercise.id))
            .where(PracticalExercise.course_id.in_(course_ids), PracticalExercise.release_key == release.key)
            .group_by(PracticalExercise.course_id)
        ).all()
    )

    practical_avgs = dict(
        db.execute(
            select(PracticalExercise.course_id, func.avg(PracticalAttempt.score / PracticalAttempt.total_points * 100))
            .join(PracticalAttempt, PracticalAttempt.exercise_id == PracticalExercise.id)
            .where(
                PracticalAttempt.user_id == current_user.id,
                PracticalExercise.course_id.in_(course_ids),
                PracticalAttempt.total_points > 0,
            )
            .group_by(PracticalExercise.course_id)
        ).all()
    )

    threads = dict(
        db.execute(
            select(DiscussionThread.course_id, func.count(DiscussionThread.id))
            .where(DiscussionThread.author_id == current_user.id, DiscussionThread.course_id.in_(course_ids))
            .group_by(DiscussionThread.course_id)
        ).all()
    )

    replies = dict(
        db.execute(
            select(DiscussionThread.course_id, func.count(DiscussionReply.id))
            .join(DiscussionReply, DiscussionReply.thread_id == DiscussionThread.id)
            .where(DiscussionReply.author_id == current_user.id, DiscussionThread.course_id.in_(course_ids))
            .group_by(DiscussionThread.course_id)
        ).all()
    )

    result = {}
    for m in memberships:
        cid = m.course_id
        result[cid] = {
            "course_id": cid,
            "resources_viewed": resource_views.get(cid, 0),
            "quizzes_taken": quiz_attempts.get(cid, 0),
            "quiz_average_percentage": round(quiz_avgs[cid], 1) if cid in quiz_avgs else None,
            "practicals_completed": practical_attempts.get(cid, 0),
            "practical_count": practical_counts.get(cid, 0),
            "practical_average_percentage": round(practical_avgs[cid], 1) if cid in practical_avgs else None,
            "discussions_participated": threads.get(cid, 0) + replies.get(cid, 0),
            "joined_at": m.joined_at,
        }
    return result
