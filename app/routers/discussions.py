from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import CONTENT_ROLES, CurrentUser, SessionDep, require_course_membership, require_experimental_group
from app.serializers import serialize_reply, serialize_thread
from app.utils import log_activity
from model import Course, DiscussionReply, DiscussionThread, Membership, Notification, ReplyHelpfulVote
from schemas import DiscussionReplyCreate, DiscussionThreadCreate

router = APIRouter()


@router.get("/api/discussions")
def list_discussions(
    db: SessionDep,
    current_user: CurrentUser,
    course_id: int | None = Query(default=None),
    include_replies: bool = Query(default=True),
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
    query = select(DiscussionThread).order_by(DiscussionThread.created_at.desc())
    if course_id is not None:
        query = query.where(DiscussionThread.course_id == course_id)
    elif joined_course_ids is not None:
        query = query.where(DiscussionThread.course_id.in_(joined_course_ids))
    threads = db.scalars(query).all()
    return [serialize_thread(thread, include_replies=include_replies) for thread in threads]


@router.post("/api/discussions")
def create_discussion(payload: DiscussionThreadCreate, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    require_course_membership(db, current_user, payload.course_id)

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
    require_experimental_group(current_user)
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")
    require_course_membership(db, current_user, thread.course_id)

    reply = DiscussionReply(thread_id=thread_id, author_id=current_user.id, body=payload.body)
    thread.updated_at = datetime.utcnow()
    db.add(reply)
    db.flush()

    if thread.author_id != current_user.id:
        db.add(Notification(
            user_id=thread.author_id,
            message=f"{current_user.full_name} replied to your discussion '{thread.title}'.",
            kind="reply",
            entity_type="discussion",
            entity_id=thread.id,
        ))

    log_activity(db, current_user, "discussion_reply_created", "reply", reply.id, {"thread_id": thread_id})
    db.commit()
    db.refresh(reply)
    return serialize_reply(reply)


@router.post("/api/discussions/{thread_id}/resolve")
def resolve_discussion(thread_id: int, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")
    if thread.author_id != current_user.id and current_user.role not in CONTENT_ROLES:
        raise HTTPException(status_code=403, detail="Only the author or a facilitator can resolve this discussion.")
    require_course_membership(db, current_user, thread.course_id)

    thread.is_resolved = True
    thread.updated_at = datetime.utcnow()
    log_activity(db, current_user, "discussion_resolved", "discussion", thread_id)
    db.commit()
    db.refresh(thread)
    return serialize_thread(thread)


@router.post("/api/replies/{reply_id}/helpful")
def mark_reply_helpful(reply_id: int, db: SessionDep, current_user: CurrentUser):
    require_experimental_group(current_user)
    reply = db.get(DiscussionReply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found.")
    require_course_membership(db, current_user, reply.thread.course_id)

    existing = db.scalar(
        select(ReplyHelpfulVote).where(ReplyHelpfulVote.reply_id == reply_id, ReplyHelpfulVote.user_id == current_user.id)
    )
    if existing:
        return {"message": "Reply already marked as helpful.", "reply": serialize_reply(reply)}

    db.add(ReplyHelpfulVote(reply_id=reply_id, user_id=current_user.id))
    reply.helpful_count += 1

    if reply.author_id != current_user.id:
        db.add(Notification(
            user_id=reply.author_id,
            message=f"{current_user.full_name} marked your reply as helpful.",
            kind="helpful",
            entity_type="reply",
            entity_id=reply_id,
        ))

    log_activity(db, current_user, "reply_marked_helpful", "reply", reply_id)
    db.commit()
    db.refresh(reply)
    return {"message": "Marked as helpful.", "reply": serialize_reply(reply)}
