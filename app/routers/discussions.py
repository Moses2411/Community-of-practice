from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import CONTENT_ROLES, CurrentUser, SessionDep
from app.serializers import serialize_reply, serialize_thread
from app.utils import log_activity
from model import Course, DiscussionReply, DiscussionThread, ReplyHelpfulVote
from schemas import DiscussionReplyCreate, DiscussionThreadCreate

router = APIRouter()


@router.get("/api/discussions")
def list_discussions(
    db: SessionDep,
    course_id: int | None = Query(default=None),
    include_replies: bool = Query(default=True),
):
    query = select(DiscussionThread).order_by(DiscussionThread.created_at.desc())
    if course_id is not None:
        query = query.where(DiscussionThread.course_id == course_id)
    threads = db.scalars(query).all()
    return [serialize_thread(thread, include_replies=include_replies) for thread in threads]


@router.post("/api/discussions")
def create_discussion(payload: DiscussionThreadCreate, db: SessionDep, current_user: CurrentUser):
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    thread = DiscussionThread(
        course_id=payload.course_id,
        author_id=current_user.id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
    )
    db.add(thread)
    db.flush()
    log_activity(db, current_user, "discussion_created", "discussion", thread.id, {"course_id": payload.course_id})
    db.commit()
    db.refresh(thread)
    return serialize_thread(thread)


@router.post("/api/discussions/{thread_id}/replies")
def create_reply(thread_id: int, payload: DiscussionReplyCreate, db: SessionDep, current_user: CurrentUser):
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    reply = DiscussionReply(thread_id=thread_id, author_id=current_user.id, body=payload.body)
    thread.updated_at = datetime.utcnow()
    db.add(reply)
    db.flush()
    log_activity(db, current_user, "discussion_reply_created", "reply", reply.id, {"thread_id": thread_id})
    db.commit()
    db.refresh(reply)
    return serialize_reply(reply)


@router.post("/api/discussions/{thread_id}/resolve")
def resolve_discussion(thread_id: int, db: SessionDep, current_user: CurrentUser):
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")
    if thread.author_id != current_user.id and current_user.role not in CONTENT_ROLES:
        raise HTTPException(status_code=403, detail="Only the author or a facilitator can resolve this discussion.")

    thread.is_resolved = True
    thread.updated_at = datetime.utcnow()
    log_activity(db, current_user, "discussion_resolved", "discussion", thread_id)
    db.commit()
    db.refresh(thread)
    return serialize_thread(thread)


@router.post("/api/replies/{reply_id}/helpful")
def mark_reply_helpful(reply_id: int, db: SessionDep, current_user: CurrentUser):
    reply = db.get(DiscussionReply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found.")

    existing = db.scalar(
        select(ReplyHelpfulVote).where(ReplyHelpfulVote.reply_id == reply_id, ReplyHelpfulVote.user_id == current_user.id)
    )
    if existing:
        return {"message": "Reply already marked as helpful.", "reply": serialize_reply(reply)}

    db.add(ReplyHelpfulVote(reply_id=reply_id, user_id=current_user.id))
    reply.helpful_count += 1
    log_activity(db, current_user, "reply_marked_helpful", "reply", reply_id)
    db.commit()
    db.refresh(reply)
    return {"message": "Marked as helpful.", "reply": serialize_reply(reply)}
