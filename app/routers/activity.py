from fastapi import APIRouter

from app.dependencies import CurrentUser, SessionDep
from app.utils import log_activity
from schemas import ActivityCreate

router = APIRouter()


@router.post("/api/activity")
def create_activity(payload: ActivityCreate, db: SessionDep, current_user: CurrentUser):
    event = log_activity(
        db,
        current_user,
        payload.action,
        payload.entity_type,
        payload.entity_id,
        payload.metadata,
    )
    db.commit()
    db.refresh(event)
    return {"message": "Activity recorded.", "id": event.id}
