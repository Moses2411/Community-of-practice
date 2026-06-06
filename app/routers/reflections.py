from fastapi import APIRouter

from app.dependencies import CurrentUser, SessionDep
from app.utils import log_activity
from model import Reflection
from schemas import ReflectionCreate

router = APIRouter()


@router.post("/api/reflections")
def create_reflection(payload: ReflectionCreate, db: SessionDep, current_user: CurrentUser):
    reflection = Reflection(
        user_id=current_user.id,
        week_label=payload.week_label,
        learned=payload.learned,
        challenge=payload.challenge,
        community_help=payload.community_help,
        confidence_rating=payload.confidence_rating,
        engagement_rating=payload.engagement_rating,
        suggestions=payload.suggestions,
    )
    db.add(reflection)
    db.flush()
    log_activity(
        db,
        current_user,
        "reflection_submitted",
        "reflection",
        reflection.id,
        {"confidence_rating": payload.confidence_rating, "engagement_rating": payload.engagement_rating},
    )
    db.commit()
    db.refresh(reflection)
    return reflection
