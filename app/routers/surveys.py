from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import CurrentUser, SessionDep
from app.utils import log_activity
from model import Survey, SurveyAnswer, SurveyQuestion, SurveyResponse
from schemas import SurveySubmit

router = APIRouter()


def serialize_survey_question(question: SurveyQuestion) -> dict:
    return {
        "id": question.id,
        "prompt": question.prompt,
        "dimension": question.dimension,
        "order_index": question.order_index,
    }


def serialize_survey(survey: Survey, include_questions: bool = False) -> dict:
    return {
        "id": survey.id,
        "title": survey.title,
        "survey_type": survey.survey_type,
        "description": survey.description,
        "is_active": survey.is_active,
        "question_count": len(survey.questions),
        "questions": [serialize_survey_question(q) for q in survey.questions] if include_questions else [],
    }


def serialize_survey_response(response: SurveyResponse) -> dict:
    dimension_scores = {}
    for answer in response.answers:
        dim = answer.question.dimension or "general"
        dimension_scores.setdefault(dim, []).append(answer.rating)
    dimension_scores = {
        dim: round(sum(ratings) / len(ratings), 2) for dim, ratings in dimension_scores.items()
    }
    return {
        "id": response.id,
        "survey_id": response.survey_id,
        "user_id": response.user_id,
        "completed_at": response.completed_at,
        "dimension_scores": dimension_scores,
    }


@router.get("/api/surveys")
def list_surveys(db: SessionDep):
    surveys = db.scalars(select(Survey).where(Survey.is_active == True).order_by(Survey.created_at)).all()
    return [
        {
            **serialize_survey(survey, include_questions=False),
            "user_has_responded": False,
        }
        for survey in surveys
    ]


@router.get("/api/surveys/{survey_id}")
def get_survey(survey_id: int, db: SessionDep, current_user: CurrentUser):
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status_code=404, detail="Survey not found.")

    already_responded = db.scalar(
        select(SurveyResponse.id).where(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.user_id == current_user.id,
        )
    ) is not None

    return {
        **serialize_survey(survey, include_questions=True),
        "user_has_responded": already_responded,
    }


@router.post("/api/surveys/{survey_id}/submit")
def submit_survey(survey_id: int, payload: SurveySubmit, db: SessionDep, current_user: CurrentUser):
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status_code=404, detail="Survey not found.")

    existing = db.scalar(
        select(SurveyResponse.id).where(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.user_id == current_user.id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted this survey.")

    response = SurveyResponse(survey_id=survey_id, user_id=current_user.id)
    db.add(response)
    db.flush()

    question_ids = {q.id for q in survey.questions}
    for answer_data in payload.answers:
        if answer_data.question_id not in question_ids:
            raise HTTPException(status_code=400, detail=f"Question {answer_data.question_id} not in this survey.")
        db.add(SurveyAnswer(
            response_id=response.id,
            question_id=answer_data.question_id,
            rating=answer_data.rating,
        ))

    log_activity(db, current_user, "survey_submitted", "survey", survey_id, {"survey_type": survey.survey_type})
    db.commit()
    db.refresh(response)
    return serialize_survey_response(response)


@router.get("/api/survey-responses")
def list_survey_responses(db: SessionDep, current_user: CurrentUser):
    responses = db.scalars(
        select(SurveyResponse)
        .where(SurveyResponse.user_id == current_user.id)
        .order_by(SurveyResponse.completed_at.desc())
    ).all()
    return [serialize_survey_response(r) for r in responses]
