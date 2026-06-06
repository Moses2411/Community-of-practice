from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, SessionDep
from app.serializers import serialize_user
from app.utils import create_access_token, generate_research_id, hash_password, log_activity, normalized_email, verify_password
from model import ConsentRecord, User
from schemas import ConsentCreate, UserCreate, UserLogin

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
