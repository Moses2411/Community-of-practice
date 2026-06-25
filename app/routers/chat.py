import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, SessionDep, require_course_membership
from app.serializers import serialize_chat_message
from app.utils import log_activity
from model import ChatMessage, Course, User
from schemas import ChatMessageCreate

router = APIRouter()

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".txt"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: CurrentUser,
):
    ext = os.path.splitext(file.filename or "file")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not allowed.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 5 MB limit.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / unique_name
    dest.write_bytes(content)

    type_map = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".doc": "doc", ".docx": "doc", ".txt": "text"}
    return {
        "url": f"/uploads/{unique_name}",
        "name": file.filename,
        "type": type_map.get(ext, "file"),
    }


@router.get("/api/courses/{course_id}/chat")
def list_chat_messages(
    course_id: int,
    db: SessionDep,
    current_user: CurrentUser,
    before: int | None = Query(default=None),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    require_course_membership(db, current_user, course_id)

    query = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.author))
        .where(ChatMessage.course_id == course_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(100)
    )
    if before is not None:
        query = query.where(ChatMessage.id < before)
    messages = db.scalars(query).all()
    return [serialize_chat_message(msg) for msg in messages]


@router.post("/api/courses/{course_id}/chat")
def send_chat_message(
    course_id: int,
    payload: ChatMessageCreate,
    db: SessionDep,
    current_user: CurrentUser,
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    require_course_membership(db, current_user, course_id)

    msg = ChatMessage(
        course_id=course_id,
        author_id=current_user.id,
        body=payload.body.strip() if payload.body else "",
        attachment_url=payload.attachment_url,
        attachment_name=payload.attachment_name,
        attachment_type=payload.attachment_type,
    )
    db.add(msg)
    db.flush()
    log_activity(db, current_user, "chat_message_sent", "chat_message", msg.id, {"course_id": course_id})
    db.commit()
    db.refresh(msg)
    msg = db.scalar(select(ChatMessage).options(selectinload(ChatMessage.author)).where(ChatMessage.id == msg.id))
    return serialize_chat_message(msg)
