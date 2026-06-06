from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import ContentManagerUser, CurrentUser, SessionDep
from app.serializers import serialize_course
from app.utils import log_activity
from model import Course, Membership
from schemas import CourseCreate, MembershipCreate

router = APIRouter()


@router.get("/api/courses")
def list_courses(db: SessionDep):
    courses = db.scalars(select(Course).order_by(Course.title)).all()
    return [serialize_course(course) for course in courses]


@router.post("/api/courses")
def create_course(payload: CourseCreate, db: SessionDep, current_user: ContentManagerUser):
    course = Course(
        title=payload.title.strip(),
        code=payload.code.strip().upper(),
        description=payload.description,
        facilitator=payload.facilitator,
    )
    db.add(course)
    try:
        db.flush()
        log_activity(db, current_user, "course_created", "course", course.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this title or code already exists.") from exc
    db.refresh(course)
    return serialize_course(course)


@router.post("/api/courses/{course_id}/join")
def join_course(course_id: int, payload: MembershipCreate, db: SessionDep, current_user: CurrentUser):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    existing = db.scalar(
        select(Membership).where(Membership.course_id == course_id, Membership.user_id == current_user.id)
    )
    if existing:
        return {"message": "Already joined this course.", "course": serialize_course(course)}

    membership = Membership(user_id=current_user.id, course_id=course_id, learning_goal=payload.learning_goal)
    db.add(membership)
    log_activity(db, current_user, "course_joined", "course", course_id, {"learning_goal": payload.learning_goal})
    db.commit()
    db.refresh(course)
    return {"message": "Course joined.", "course": serialize_course(course)}
