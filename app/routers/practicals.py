import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import CONTENT_ROLES, CurrentUser, SessionDep, require_course_membership, require_experimental_group
from app.practical_schedule import ensure_daily_practicals
from app.serializers import practical_attempt_response, serialize_practical_exercise
from app.utils import log_activity
from model import Course, Membership, PracticalAttempt, PracticalExercise, Quiz, QuizAttempt, ResourceView
from schemas import PracticalSubmit

router = APIRouter()


def evaluate_submission(exercise: PracticalExercise, submitted_code: str) -> tuple[float, list[dict]]:
    try:
        checks = json.loads(exercise.checks_json or "[]")
    except json.JSONDecodeError:
        checks = []

    if not checks:
        return 100.0, [{"label": "Submitted", "passed": True, "message": "Submission received for review."}]

    feedback = []
    passed = 0
    for check in checks:
        text = submitted_code if check.get("case_sensitive") else submitted_code.lower()
        contains_all = check.get("contains_all") or []
        contains_any = check.get("contains_any") or []
        normalized_all = [item if check.get("case_sensitive") else str(item).lower() for item in contains_all]
        normalized_any = [item if check.get("case_sensitive") else str(item).lower() for item in contains_any]

        all_passed = all(item in text for item in normalized_all)
        any_passed = True if not normalized_any else any(item in text for item in normalized_any)
        check_passed = all_passed and any_passed
        if check_passed:
            passed += 1
        feedback.append(
            {
                "label": check.get("label", "Check"),
                "passed": check_passed,
                "message": "Met" if check_passed else "Needs improvement",
            }
        )

    return round((passed / len(checks)) * 100, 2), feedback


@router.get("/api/practicals")
def list_practicals(
    db: SessionDep,
    current_user: CurrentUser,
    course_id: int | None = Query(default=None),
    practical_type: str | None = Query(default=None),
):
    require_experimental_group(current_user)
    joined_course_ids = None
    active_course_ids: list[int] = []
    if current_user.role not in CONTENT_ROLES:
        joined_course_ids = set(
            db.scalars(select(Membership.course_id).where(Membership.user_id == current_user.id)).all()
        )
        if course_id is not None and course_id not in joined_course_ids:
            raise HTTPException(status_code=403, detail="You must join this course first.")
        active_course_ids = [course_id] if course_id is not None else list(joined_course_ids)
    elif course_id is not None:
        active_course_ids = [course_id]
    else:
        active_course_ids = db.scalars(select(Course.id)).all()

    release = ensure_daily_practicals(db, active_course_ids)

    query = (
        select(PracticalExercise)
        .options(
            selectinload(PracticalExercise.course),
            selectinload(PracticalExercise.attempts),
        )
        .where(PracticalExercise.release_key == release.key)
        .order_by(PracticalExercise.course_id, PracticalExercise.practical_type, PracticalExercise.difficulty, PracticalExercise.title)
    )
    if course_id is not None:
        query = query.where(PracticalExercise.course_id == course_id)
    elif joined_course_ids is not None:
        query = query.where(PracticalExercise.course_id.in_(joined_course_ids))
    if practical_type:
        if practical_type == "coding":
            query = query.where(PracticalExercise.practical_type.in_(["python", "java"]))
        else:
            query = query.where(PracticalExercise.practical_type == practical_type)

    exercises = db.scalars(query).all()
    include_solution = current_user.role in CONTENT_ROLES
    return [
        serialize_practical_exercise(exercise, user_id=current_user.id, include_solution=include_solution)
        for exercise in exercises
    ]


@router.get("/api/practicals/attempts")
def list_practical_attempts(db: SessionDep, current_user: CurrentUser):
    attempts = db.scalars(
        select(PracticalAttempt)
        .join(PracticalExercise, PracticalAttempt.exercise_id == PracticalExercise.id)
        .options(
            selectinload(PracticalAttempt.exercise).selectinload(PracticalExercise.course),
        )
        .where(PracticalAttempt.user_id == current_user.id)
        .order_by(PracticalAttempt.completed_at.desc())
    ).all()
    return [practical_attempt_response(attempt) for attempt in attempts]


@router.post("/api/practicals/{exercise_id}/submit")
def submit_practical(exercise_id: int, payload: PracticalSubmit, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    exercise = db.get(PracticalExercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Practical exercise not found.")
    require_course_membership(db, current_user, exercise.course_id)

    score, feedback = evaluate_submission(exercise, payload.submitted_code)
    attempt = PracticalAttempt(
        exercise_id=exercise.id,
        user_id=current_user.id,
        submitted_code=payload.submitted_code,
        score=score,
        total_points=100,
        feedback_json=json.dumps(feedback),
    )
    db.add(attempt)
    log_activity(
        db,
        current_user,
        "practical_submitted",
        "practical_exercise",
        exercise.id,
        {"practical_type": exercise.practical_type, "score": score},
    )
    db.commit()
    db.refresh(attempt)
    return practical_attempt_response(attempt)


@router.get("/api/performance")
def performance_summary(db: SessionDep, current_user: CurrentUser):
    memberships = db.scalars(
        select(Membership)
        .options(selectinload(Membership.course).selectinload(Course.resources))
        .where(Membership.user_id == current_user.id)
    ).all()
    if not memberships:
        return {"strong": [], "needs_improvement": [], "courses": []}

    rows = []
    for membership in memberships:
        course = membership.course
        quiz_average = db.scalar(
            select(func.avg(QuizAttempt.score / QuizAttempt.total_points * 100))
            .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == current_user.id, Quiz.course_id == course.id, QuizAttempt.total_points > 0)
        )
        practical_average = db.scalar(
            select(func.avg(PracticalAttempt.score / PracticalAttempt.total_points * 100))
            .join(PracticalExercise, PracticalAttempt.exercise_id == PracticalExercise.id)
            .where(
                PracticalAttempt.user_id == current_user.id,
                PracticalExercise.course_id == course.id,
                PracticalAttempt.total_points > 0,
            )
        )
        resource_views = db.scalar(
            select(func.count(ResourceView.id)).where(
                ResourceView.user_id == current_user.id,
                ResourceView.resource.has(course_id=course.id),
            )
        ) or 0
        resource_count = len(course.resources)
        resource_percentage = (resource_views / resource_count * 100) if resource_count else 0

        scored = [value for value in [quiz_average, practical_average] if value is not None]
        performance_score = round(sum(scored) / len(scored), 1) if scored else None
        if performance_score is None:
            status = "not_started"
        elif performance_score >= 70:
            status = "strong"
        elif performance_score >= 50:
            status = "steady"
        else:
            status = "needs_improvement"

        rows.append(
            {
                "course_id": course.id,
                "course_code": course.code,
                "course_title": course.title,
                "status": status,
                "performance_score": performance_score,
                "quiz_average_percentage": round(float(quiz_average), 1) if quiz_average is not None else None,
                "practical_average_percentage": round(float(practical_average), 1) if practical_average is not None else None,
                "resource_percentage": round(resource_percentage, 1),
                "resources_viewed": resource_views,
                "resource_count": resource_count,
            }
        )

    return {
        "strong": [row for row in rows if row["status"] == "strong"],
        "needs_improvement": [row for row in rows if row["status"] in {"needs_improvement", "not_started"}],
        "courses": rows,
    }
