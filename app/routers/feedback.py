from fastapi import APIRouter

from app.dependencies import CurrentUser, SessionDep
from app.utils import log_activity
from model import PlatformFeedback
from schemas import PlatformFeedbackCreate

router = APIRouter()


@router.post("/api/feedback")
def create_platform_feedback(payload: PlatformFeedbackCreate, db: SessionDep, current_user: CurrentUser):
    feedback = PlatformFeedback(
        user_id=current_user.id,
        category=payload.category,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.flush()
    log_activity(
        db,
        current_user,
        "platform_feedback_submitted",
        "platform_feedback",
        feedback.id,
        {"category": payload.category, "rating": payload.rating},
    )
    db.commit()
    db.refresh(feedback)
    return {"message": "Platform feedback recorded.", "id": feedback.id}
