from datetime import datetime, timedelta
import random
import string

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, ResearcherUser, SessionDep
from app.serializers import serialize_user
from app.utils import create_access_token, generate_research_id, hash_password, log_activity, normalized_email, verify_password
from model import ConsentRecord, PasswordResetToken, User
from schemas import (
    AdminPasswordReset,
    ChangePassword,
    ConsentCreate,
    GenerateResetToken,
    SecurityAnswerCheck,
    SecurityPasswordReset,
    TokenPasswordReset,
    UserCreate,
    UserLogin,
)

router = APIRouter()


@router.post("/api/auth/register")
def register(payload: UserCreate, db: SessionDep):
    if not payload.accepted_research_consent:
        raise HTTPException(status_code=400, detail="Research consent is required before registration.")

    user = User(
        research_id=generate_research_id(db),
        full_name=payload.full_name.strip(),
        email=normalized_email(payload.email),
        password_hash=hash_password(payload.password),
        role="student",
        study_group=payload.study_group,
        programme=payload.programme,
        department=payload.department,
        level=payload.level,
        interests=payload.interests,
        security_question=payload.security_question,
        security_answer_hash=hash_password(payload.security_answer) if payload.security_answer else None,
    )
    db.add(user)
    try:
        db.flush()
        db.add(ConsentRecord(user_id=user.id, agreed=True, consent_version="v1"))
        log_activity(db, user, "registered", "user", user.id, {"study_group": user.study_group})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc

    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize_user(user)}


@router.post("/api/auth/login")
def login(payload: UserLogin, db: SessionDep):
    user = db.scalar(select(User).where(User.email == normalized_email(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user.last_login_at = datetime.utcnow()
    log_activity(db, user, "logged_in", "user", user.id)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize_user(user)}


@router.get("/api/me")
def me(current_user: CurrentUser):
    return serialize_user(current_user)


@router.post("/api/consent")
def record_consent(payload: ConsentCreate, db: SessionDep, current_user: CurrentUser):
    consent = ConsentRecord(
        user_id=current_user.id,
        consent_version=payload.consent_version,
        agreed=payload.agreed,
        notes=payload.notes,
    )
    db.add(consent)
    log_activity(db, current_user, "consent_recorded", "consent", None, {"agreed": payload.agreed})
    db.commit()
    db.refresh(consent)
    return {"id": consent.id, "agreed": consent.agreed, "consent_version": consent.consent_version}


@router.post("/api/auth/change-password")
def change_password(payload: ChangePassword, db: SessionDep, current_user: CurrentUser):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.password_hash = hash_password(payload.new_password)
    log_activity(db, current_user, "password_changed", "user", current_user.id)
    db.commit()
    return {"message": "Password updated."}


@router.get("/api/auth/security-question")
def get_security_question(email: str, db: SessionDep):
    user = db.scalar(select(User).where(User.email == normalized_email(email)))
    if user is None or not user.security_question:
        raise HTTPException(status_code=404, detail="No security question found for this email.")
    return {"question": user.security_question}


@router.post("/api/auth/reset-with-security")
def reset_with_security(payload: SecurityPasswordReset, db: SessionDep):
    user = db.scalar(select(User).where(User.email == normalized_email(payload.email)))
    if user is None or not user.security_answer_hash:
        raise HTTPException(status_code=400, detail="Password reset not available for this account.")
    if not verify_password(payload.answer, user.security_answer_hash):
        raise HTTPException(status_code=400, detail="Incorrect answer.")
    user.password_hash = hash_password(payload.new_password)
    log_activity(db, user, "password_reset_security", "user", user.id)
    db.commit()
    return {"message": "Password reset successfully."}


@router.post("/api/admin/users/{user_id}/generate-reset-token")
def generate_reset_token(user_id: int, db: SessionDep, current_user: ResearcherUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    token = PasswordResetToken(
        user_id=user.id,
        code=code,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(token)
    log_activity(db, current_user, "reset_token_generated", "user", user.id)
    db.commit()
    return {"code": code, "expires_in_hours": 24}


@router.post("/api/auth/reset-with-token")
def reset_with_token(payload: TokenPasswordReset, db: SessionDep):
    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.code == payload.code,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
    )
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.password_hash = hash_password(payload.new_password)
    token.used = True
    log_activity(db, user, "password_reset_token", "user", user.id)
    db.commit()
    return {"message": "Password reset successfully."}


@router.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, payload: AdminPasswordReset, db: SessionDep, current_user: ResearcherUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.password_hash = hash_password(payload.new_password)
    log_activity(db, current_user, "password_reset_admin", "user", user_id, {"reset_by": current_user.research_id})
    db.commit()
    return {"message": f"Password reset for {user.research_id}."}
