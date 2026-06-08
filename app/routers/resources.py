from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import ContentManagerUser, CurrentUser, SessionDep, CONTENT_ROLES, require_course_membership
from app.serializers import serialize_resource
from app.utils import log_activity
from model import Course, Membership, Resource, ResourceFeedback, ResourceView
from schemas import ResourceCreate, ResourceFeedbackCreate

router = APIRouter()


@router.get("/api/resources")
def list_resources(db: SessionDep, current_user: CurrentUser, course_id: int | None = Query(default=None)):
    joined_course_ids = None
    if current_user.role not in CONTENT_ROLES:
        memberships = db.scalars(
            select(Membership.course_id).where(Membership.user_id == current_user.id)
        ).all()
        joined_course_ids = set(memberships)
        if course_id is not None and course_id not in joined_course_ids:
            raise HTTPException(status_code=403, detail="You must join this course first.")
    query = select(Resource).order_by(Resource.created_at.desc())
    if course_id is not None:
        query = query.where(Resource.course_id == course_id)
    elif joined_course_ids is not None:
        query = query.where(Resource.course_id.in_(joined_course_ids))
    resources = db.scalars(query).all()
    return [serialize_resource(resource) for resource in resources]


@router.post("/api/resources")
def create_resource(payload: ResourceCreate, db: SessionDep, current_user: ContentManagerUser):
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    resource = Resource(
        course_id=payload.course_id,
        created_by_id=current_user.id,
        title=payload.title,
        resource_type=payload.resource_type,
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
        url=payload.url,
        video_url=payload.video_url,
        blog_url=payload.blog_url,
        body=payload.body,
    )
    db.add(resource)
    db.flush()
    log_activity(db, current_user, "resource_created", "resource", resource.id, {"course_id": payload.course_id})
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource)


@router.get("/api/resources/{resource_id}")
def get_resource(
    resource_id: int,
    db: SessionDep,
    current_user: CurrentUser,
    seconds_spent: int = Query(default=0, ge=0),
):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    require_course_membership(db, current_user, resource.course_id)

    view = ResourceView(resource_id=resource.id, user_id=current_user.id, seconds_spent=seconds_spent)
    db.add(view)
    log_activity(
        db,
        current_user,
        "resource_viewed",
        "resource",
        resource.id,
        {"course_id": resource.course_id, "seconds_spent": seconds_spent},
    )
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource)


@router.post("/api/resources/{resource_id}/feedback")
def submit_resource_feedback(
    resource_id: int,
    payload: ResourceFeedbackCreate,
    db: SessionDep,
    current_user: CurrentUser,
):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    require_course_membership(db, current_user, resource.course_id)

    feedback = ResourceFeedback(
        resource_id=resource_id,
        user_id=current_user.id,
        usefulness_rating=payload.usefulness_rating,
        clarity_rating=payload.clarity_rating,
        confidence_after=payload.confidence_after,
        comment=payload.comment,
    )
    db.add(feedback)
    log_activity(
        db,
        current_user,
        "resource_feedback_submitted",
        "resource",
        resource_id,
        {"usefulness_rating": payload.usefulness_rating, "clarity_rating": payload.clarity_rating},
    )
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback recorded.", "id": feedback.id}
