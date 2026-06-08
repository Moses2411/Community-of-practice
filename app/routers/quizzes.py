from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from app.dependencies import CONTENT_ROLES, ContentManagerUser, CurrentUser, RESEARCH_ROLES, SessionDep, require_course_membership, require_experimental_group
from app.serializers import quiz_attempt_response, serialize_quiz
from app.utils import log_activity, select_round_questions
from model import Course, Membership, Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from schemas import QuizCreate, QuizQuestionCreate, QuizSubmit

router = APIRouter()


@router.get("/api/quizzes")
def list_quizzes(
    db: SessionDep,
    current_user: CurrentUser,
    course_id: int | None = Query(default=None),
    quiz_type: str | None = Query(default=None),
):
    require_experimental_group(current_user)
    joined_course_ids = None
    if current_user.role not in CONTENT_ROLES:
        memberships = db.scalars(
            select(Membership.course_id).where(Membership.user_id == current_user.id)
        ).all()
        joined_course_ids = set(memberships)
        if course_id is not None and course_id not in joined_course_ids:
            raise HTTPException(status_code=403, detail="You must join this course first.")
    query = select(Quiz).order_by(Quiz.created_at.desc())
    if course_id is not None:
        query = query.where(Quiz.course_id == course_id)
    elif joined_course_ids is not None:
        query = query.where(Quiz.course_id.in_(joined_course_ids))
    if quiz_type is not None:
        query = query.where(Quiz.quiz_type == quiz_type)
    quizzes = db.scalars(query).all()
    return [serialize_quiz(quiz) for quiz in quizzes]


@router.post("/api/quizzes")
def create_quiz(payload: QuizCreate, db: SessionDep, current_user: ContentManagerUser):
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    quiz = Quiz(
        course_id=payload.course_id,
        title=payload.title,
        quiz_type=payload.quiz_type,
        description=payload.description,
    )
    db.add(quiz)
    db.flush()
    log_activity(db, current_user, "quiz_created", "quiz", quiz.id, {"quiz_type": payload.quiz_type})
    db.commit()
    db.refresh(quiz)
    return serialize_quiz(quiz)


@router.post("/api/quizzes/{quiz_id}/questions")
def create_quiz_question(quiz_id: int, payload: QuizQuestionCreate, db: SessionDep, current_user: ContentManagerUser):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    question = QuizQuestion(
        quiz_id=quiz_id,
        prompt=payload.prompt,
        option_a=payload.option_a,
        option_b=payload.option_b,
        option_c=payload.option_c,
        option_d=payload.option_d,
        correct_option=payload.correct_option,
        explanation=payload.explanation,
        points=payload.points,
    )
    db.add(question)
    db.flush()
    log_activity(db, current_user, "quiz_question_created", "quiz_question", question.id, {"quiz_id": quiz_id})
    db.commit()
    db.refresh(quiz)
    return serialize_quiz(quiz, include_questions=True, include_answers=True)


@router.get("/api/quizzes/{quiz_id}")
def get_quiz(quiz_id: int, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    require_course_membership(db, current_user, quiz.course_id)
    include_answers = current_user.role in CONTENT_ROLES
    round_questions = select_round_questions(db, quiz, current_user)
    log_activity(db, current_user, "quiz_viewed", "quiz", quiz_id, {"quiz_type": quiz.quiz_type})
    db.commit()
    return serialize_quiz(quiz, include_questions=True, include_answers=include_answers, round_questions=round_questions)


@router.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: int, payload: QuizSubmit, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    require_course_membership(db, current_user, quiz.course_id)
    if not quiz.questions:
        raise HTTPException(status_code=400, detail="This quiz has no questions yet.")

    round_questions = select_round_questions(db, quiz, current_user)
    answer_map = {answer.question_id: answer.selected_option for answer in payload.answers}
    total_points = float(sum(question.points for question in round_questions))
    score = 0.0

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=current_user.id,
        score=0,
        total_points=total_points,
        seconds_spent=payload.seconds_spent,
        completed_at=datetime.utcnow(),
    )
    db.add(attempt)
    db.flush()

    for question in round_questions:
        selected = answer_map.get(question.id)
        is_correct = selected == question.correct_option
        points_awarded = float(question.points if is_correct else 0)
        score += points_awarded
        db.add(
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option=selected,
                is_correct=is_correct,
                points_awarded=points_awarded,
            )
        )

    attempt.score = score
    log_activity(
        db,
        current_user,
        "quiz_submitted",
        "quiz",
        quiz_id,
        {"quiz_type": quiz.quiz_type, "score": score, "total_points": total_points},
    )
    db.commit()
    db.refresh(attempt)
    return quiz_attempt_response(attempt, include_answers=True)


@router.get("/api/quiz-attempts")
def list_quiz_attempts(db: SessionDep, current_user: CurrentUser):
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.completed_at.desc())
    ).all()
    return [quiz_attempt_response(attempt) for attempt in attempts]


@router.get("/api/quiz-attempts/{attempt_id}")
def get_quiz_attempt(attempt_id: int, db: SessionDep, current_user: CurrentUser):
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    if attempt.user_id != current_user.id and current_user.role not in RESEARCH_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view this attempt.")
    return quiz_attempt_response(attempt, include_answers=True)
