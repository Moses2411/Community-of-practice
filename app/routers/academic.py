from fastapi import APIRouter, HTTPException

from app.dependencies import ResearcherUser, SessionDep
from app.utils import log_activity
from model import AcademicRecord, User
from schemas import AcademicRecordCreate

router = APIRouter()


@router.post("/api/academic-records")
def create_academic_record(payload: AcademicRecordCreate, db: SessionDep, current_user: ResearcherUser):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    record = AcademicRecord(
        user_id=payload.user_id,
        assessment_name=payload.assessment_name,
        assessment_type=payload.assessment_type,
        score=payload.score,
        total=payload.total,
        notes=payload.notes,
    )
    db.add(record)
    db.flush()
    log_activity(
        db,
        current_user,
        "academic_record_created",
        "academic_record",
        record.id,
        {"student_research_id": user.research_id, "assessment_type": payload.assessment_type},
    )
    db.commit()
    db.refresh(record)
    return {"message": "Academic record saved.", "id": record.id}
