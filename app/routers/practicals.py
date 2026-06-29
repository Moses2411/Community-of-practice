import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import func, select, text as sql_text
from sqlalchemy.orm import selectinload

from app.dependencies import CONTENT_ROLES, CurrentUser, SessionDep, require_course_membership, require_experimental_group
from app.practical_schedule import ensure_daily_practicals
from app.serializers import practical_attempt_response, serialize_practical_exercise
from app.utils import log_activity
from db.database import engine
from model import Course, Membership, PracticalAttempt, PracticalExercise, Quiz, QuizAttempt, ResourceView
from schemas import PracticalSubmit

logger = logging.getLogger(__name__)
PISTON_URL = "https://emkc.org/api/v2/piston/execute"


def execute_code_via_piston(code: str, language: str, test_code: str | None = None) -> dict[str, Any]:
    if language == "python":
        full = code + "\n\n" + (test_code or "")
        payload = {
            "language": "python",
            "version": "3.10.0",
            "files": [{"name": "main.py", "content": full}],
            "compile_timeout": 15000,
            "run_timeout": 5000,
        }
    elif language == "java":
        files = [{"name": "Practice.java", "content": code}]
        if test_code:
            files.append({"name": "Main.java", "content": test_code})
        payload = {
            "language": "java",
            "version": "15.0.2",
            "files": files,
            "compile_timeout": 20000,
            "run_timeout": 8000,
        }
    else:
        return {"error": f"Unsupported language: {language}"}

    try:
        resp = requests.post(PISTON_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("Piston API error: %s", e)
        return {"error": str(e)}


def execute_sql_in_transaction(setup_sql: str | None, submitted_sql: str) -> str:
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            if setup_sql:
                conn.execute(sql_text(setup_sql))
            result = conn.execute(sql_text(submitted_sql))
            rows = result.fetchall()
            return "\n".join(str(tuple(row)) for row in rows)
        except Exception as e:
            return f"ERROR: {e}"
        finally:
            trans.rollback()


def evaluate_submission(exercise: PracticalExercise, submitted_code: str) -> tuple[float, list[dict]]:
    try:
        checks = json.loads(exercise.checks_json or "[]")
    except json.JSONDecodeError:
        checks = []

    if not checks:
        return 100.0, [{"label": "Submitted", "passed": True, "message": "Submission received for review."}]

    feedback = []
    all_passed = True

    for check in checks:
        if check.get("run"):
            exec_type = check.get("type", exercise.practical_type)
            if exec_type == "sql":
                setup = check.get("setup_sql")
                output = execute_sql_in_transaction(setup, submitted_code)
            elif exec_type == "python":
                result = execute_code_via_piston(submitted_code, "python", check.get("test_code"))
                run_result = result.get("run") if isinstance(result.get("run"), dict) else {}
                output = run_result.get("stdout", "").strip()
                stderr = run_result.get("stderr", "").strip()
                if stderr:
                    output += "\nSTDERR: " + stderr
            elif exec_type == "java":
                result = execute_code_via_piston(submitted_code, "java", check.get("test_code"))
                run_result = result.get("run") if isinstance(result.get("run"), dict) else {}
                output = run_result.get("stdout", "").strip()
                stderr = run_result.get("stderr", "").strip()
                if stderr:
                    output += "\nSTDERR: " + stderr
            else:
                output = ""
            expected = (check.get("expected_output") or "").strip()
            passed = output == expected
            if not passed:
                all_passed = False
            feedback.append({
                "label": check.get("label", "Execution test"),
                "passed": passed,
                "message": "Passed" if passed else f"Expected '{expected}', got '{output}'",
            })
        else:
            text = submitted_code if check.get("case_sensitive") else submitted_code.lower()
            contains_all = check.get("contains_all") or []
            contains_any = check.get("contains_any") or []
            normalized_all = [item if check.get("case_sensitive") else str(item).lower() for item in contains_all]
            normalized_any = [item if check.get("case_sensitive") else str(item).lower() for item in contains_any]
            ca_passed = all(item in text for item in normalized_all)
            cy_passed = True if not normalized_any else any(item in text for item in normalized_any)
            check_passed = ca_passed and cy_passed
            if not check_passed:
                all_passed = False
            feedback.append({
                "label": check.get("label", "Check"),
                "passed": check_passed,
                "message": "Passed" if check_passed else "Failed",
            })

    score = 100.0 if all_passed else 0.0
    return score, feedback


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

    utc_now = datetime.now(timezone.utc)
    query = (
        select(PracticalExercise)
        .options(
            selectinload(PracticalExercise.course),
            selectinload(PracticalExercise.attempts),
        )
        .where(
            PracticalExercise.release_key == release.key,
            PracticalExercise.release_at <= utc_now,
            PracticalExercise.expires_at > utc_now,
        )
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
async def submit_practical(exercise_id: int, payload: PracticalSubmit, db: SessionDep, current_user: CurrentUser, dry_run: bool = Query(default=False)):
    require_experimental_group(current_user)
    exercise = db.get(PracticalExercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Practical exercise not found.")
    require_course_membership(db, current_user, exercise.course_id)

    loop = asyncio.get_event_loop()
    score, feedback = await loop.run_in_executor(None, evaluate_submission, exercise, payload.submitted_code)

    if dry_run:
        return {
            "score": score,
            "total_points": 100,
            "percentage": score,
            "feedback": feedback,
            "practical_type": exercise.practical_type,
            "exercise_title": exercise.title,
            "course_code": exercise.course.code if exercise.course else None,
            "solution_notes": None,
        }

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

    uid = current_user.id
    course_ids = [m.course_id for m in memberships]

    quiz_avgs = dict(
        db.execute(
            select(Quiz.course_id, func.avg(QuizAttempt.score / QuizAttempt.total_points * 100))
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .where(QuizAttempt.user_id == uid, Quiz.course_id.in_(course_ids), QuizAttempt.total_points > 0)
            .group_by(Quiz.course_id)
        ).all()
    )

    practical_avgs = dict(
        db.execute(
            select(PracticalExercise.course_id, func.avg(PracticalAttempt.score / PracticalAttempt.total_points * 100))
            .join(PracticalAttempt, PracticalAttempt.exercise_id == PracticalExercise.id)
            .where(PracticalAttempt.user_id == uid, PracticalExercise.course_id.in_(course_ids), PracticalAttempt.total_points > 0)
            .group_by(PracticalExercise.course_id)
        ).all()
    )

    resource_view_counts = dict(
        db.execute(
            select(Resource.course_id, func.count(ResourceView.id))
            .join(ResourceView, ResourceView.resource_id == Resource.id)
            .where(ResourceView.user_id == uid, Resource.course_id.in_(course_ids))
            .group_by(Resource.course_id)
        ).all()
    )

    rows = []
    for membership in memberships:
        course = membership.course
        quiz_average = quiz_avgs.get(course.id)
        practical_average = practical_avgs.get(course.id)
        resource_views = resource_view_counts.get(course.id, 0)
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
