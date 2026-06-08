from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.dependencies import CurrentUser, SessionDep
from model import Notification

router = APIRouter()


@router.get("/api/notifications")
def list_notifications(db: SessionDep, current_user: CurrentUser):
    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    ) or 0
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return {
        "unread_count": unread_count,
        "items": [
            {
                "id": n.id,
                "message": n.message,
                "kind": n.kind,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifications
        ],
    }


@router.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: SessionDep, current_user: CurrentUser):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.is_read = True
    db.commit()
    return {"id": notification.id, "is_read": True}


@router.post("/api/notifications/read-all")
def mark_all_read(db: SessionDep, current_user: CurrentUser):
    db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    ).all()
    for n in notifications:
        n.is_read = True
    db.commit()
    return {"message": f"{len(notifications)} notifications marked as read."}
