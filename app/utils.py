import csv
import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timedelta
from typing import Iterable

from fastapi.responses import StreamingResponse
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, QUIZ_ROUND_SIZE, SECRET_KEY
from model import ActivityLog, QuizAnswer, QuizAttempt, QuizQuestion, User


def bank_question(
    prompt: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: str,
    explanation: str,
    question_type: str = "mcq",
) -> dict:
    return {
        "prompt": prompt,
        "question_type": question_type,
        "option_a": option_a,
        "option_b": option_b,
        "option_c": option_c,
        "option_d": option_d,
        "correct_option": correct_option,
        "explanation": explanation,
        "points": 1,
    }


def theory_question(
    prompt: str,
    explanation: str = "",
) -> dict:
    return {
        "prompt": prompt,
        "question_type": "theory",
        "option_a": "",
        "option_b": "",
        "option_c": "",
        "option_d": "",
        "correct_option": None,
        "explanation": explanation,
        "points": 1,
    }


def hash_password(password: str) -> str:
    iterations = 260_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user.id), "role": user.role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_research_id(db: Session) -> str:
    year = datetime.utcnow().year
    while True:
        candidate = f"ABU-CSE-{year}-{secrets.randbelow(9000) + 1000}"
        exists = db.scalar(select(User.id).where(User.research_id == candidate))
        if not exists:
            return candidate


def normalized_email(email: str) -> str:
    return email.strip().lower()


def log_activity(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    event = ActivityLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(event)
    return event


def csv_response(filename: str, headers: list[str], rows: Iterable[Iterable]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def select_round_questions(db: Session, quiz, user: User, round_size: int = QUIZ_ROUND_SIZE, question_type: str | None = None) -> list:
    import random

    questions = list(quiz.questions)
    if question_type:
        questions = [q for q in questions if q.question_type == question_type]
    if not questions:
        return []

    if len(questions) <= round_size:
        return questions

    answered_ids = set(
        db.scalars(
            select(QuizAnswer.question_id)
            .join(QuizAttempt, QuizAnswer.attempt_id == QuizAttempt.id)
            .where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == user.id)
        ).all()
    )
    unseen_questions = [q for q in questions if q.id not in answered_ids]
    pool = unseen_questions if len(unseen_questions) >= round_size else questions
    if len(pool) > round_size:
        pool = random.sample(pool, round_size)
    return pool
