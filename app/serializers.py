import json

from model import (
    Course,
    DiscussionReply,
    DiscussionThread,
    PracticalAttempt,
    PracticalExercise,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Resource,
    User,
)
from app.config import QUIZ_ROUND_SIZE


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "research_id": user.research_id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "study_group": user.study_group,
        "programme": user.programme,
        "department": user.department,
        "level": user.level,
        "interests": user.interests,
        "created_at": user.created_at,
    }


def serialize_course(course: Course, user_id: int | None = None) -> dict:
    is_joined = False
    learning_goal = None
    if user_id is not None:
        for m in course.memberships:
            if m.user_id == user_id:
                is_joined = True
                learning_goal = m.learning_goal
                break
    return {
        "id": course.id,
        "title": course.title,
        "code": course.code,
        "description": course.description,
        "facilitator": course.facilitator,
        "created_at": course.created_at,
        "member_count": len(course.memberships),
        "resource_count": len(course.resources),
        "discussion_count": len(course.threads),
        "practical_count": len(course.practical_exercises),
        "is_joined": is_joined,
        "learning_goal": learning_goal,
    }


def serialize_resource(resource: Resource) -> dict:
    ratings = [feedback.usefulness_rating for feedback in resource.feedback]
    average_usefulness = round(sum(ratings) / len(ratings), 2) if ratings else None
    return {
        "id": resource.id,
        "course_id": resource.course_id,
        "title": resource.title,
        "resource_type": resource.resource_type,
        "difficulty": resource.difficulty,
        "estimated_minutes": resource.estimated_minutes,
        "url": resource.url,
        "video_url": resource.video_url,
        "blog_url": resource.blog_url,
        "body": resource.body,
        "created_at": resource.created_at,
        "average_usefulness": average_usefulness,
        "view_count": len(resource.views),
    }


def serialize_reply(reply: DiscussionReply) -> dict:
    return {
        "id": reply.id,
        "thread_id": reply.thread_id,
        "author_id": reply.author_id,
        "author_name": reply.author.full_name if reply.author else None,
        "body": reply.body,
        "helpful_count": reply.helpful_count,
        "created_at": reply.created_at,
    }


def serialize_thread(thread: DiscussionThread, include_replies: bool = True) -> dict:
    return {
        "id": thread.id,
        "course_id": thread.course_id,
        "author_id": thread.author_id,
        "author_name": thread.author.full_name if thread.author else None,
        "title": thread.title,
        "body": thread.body,
        "tags": thread.tags,
        "is_resolved": thread.is_resolved,
        "created_at": thread.created_at,
        "reply_count": len(thread.replies),
        "replies": [serialize_reply(reply) for reply in thread.replies] if include_replies else [],
    }


def serialize_quiz_question(question: QuizQuestion, include_answers: bool = False) -> dict:
    return {
        "id": question.id,
        "prompt": question.prompt,
        "option_a": question.option_a,
        "option_b": question.option_b,
        "option_c": question.option_c,
        "option_d": question.option_d,
        "points": question.points,
        "explanation": question.explanation if include_answers else None,
        "correct_option": question.correct_option if include_answers else None,
    }


def serialize_quiz(
    quiz: Quiz,
    include_questions: bool = False,
    include_answers: bool = False,
    round_questions: list[QuizQuestion] | None = None,
) -> dict:
    questions = []
    if include_questions:
        selected = round_questions if round_questions is not None else list(quiz.questions)
        questions = [serialize_quiz_question(q, include_answers=include_answers) for q in selected]
    return {
        "id": quiz.id,
        "course_id": quiz.course_id,
        "title": quiz.title,
        "quiz_type": quiz.quiz_type,
        "description": quiz.description,
        "created_at": quiz.created_at,
        "question_count": len(quiz.questions),
        "round_size": min(QUIZ_ROUND_SIZE, len(quiz.questions)),
        "questions": questions,
    }


def quiz_attempt_response(attempt: QuizAttempt, include_answers: bool = False) -> dict:
    percentage = (attempt.score / attempt.total_points * 100) if attempt.total_points else 0
    payload = {
        "id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "quiz_title": attempt.quiz.title,
        "quiz_type": attempt.quiz.quiz_type,
        "course_id": attempt.quiz.course_id,
        "course_title": attempt.quiz.course.title if attempt.quiz.course else None,
        "course_code": attempt.quiz.course.code if attempt.quiz.course else None,
        "user_id": attempt.user_id,
        "score": attempt.score,
        "total_points": attempt.total_points,
        "percentage": round(percentage, 2),
        "seconds_spent": attempt.seconds_spent,
        "question_count": len(attempt.answers),
        "completed_at": attempt.completed_at,
    }
    if include_answers:
        payload["answers"] = [
            {
                "question_id": answer.question_id,
                "prompt": answer.question.prompt,
                "selected_option": answer.selected_option,
                "correct_option": answer.question.correct_option,
                "is_correct": answer.is_correct,
                "points_awarded": answer.points_awarded,
                "points": answer.question.points,
                "explanation": answer.question.explanation,
                "options": {
                    "a": answer.question.option_a,
                    "b": answer.question.option_b,
                    "c": answer.question.option_c,
                    "d": answer.question.option_d,
                },
            }
            for answer in attempt.answers
        ]
    return payload


def serialize_practical_exercise(
    exercise: PracticalExercise,
    user_id: int | None = None,
    include_solution: bool = False,
) -> dict:
    checks = []
    if exercise.checks_json:
        try:
            checks = json.loads(exercise.checks_json)
        except json.JSONDecodeError:
            checks = []

    user_attempts = [attempt for attempt in exercise.attempts if attempt.user_id == user_id] if user_id else []
    percentages = [
        attempt.score / attempt.total_points * 100
        for attempt in user_attempts
        if attempt.total_points
    ]

    return {
        "id": exercise.id,
        "course_id": exercise.course_id,
        "course_code": exercise.course.code if exercise.course else None,
        "course_title": exercise.course.title if exercise.course else None,
        "title": exercise.title,
        "practical_type": exercise.practical_type,
        "difficulty": exercise.difficulty,
        "prompt": exercise.prompt,
        "starter_code": exercise.starter_code,
        "expected_output": exercise.expected_output,
        "solution_notes": exercise.solution_notes if include_solution else None,
        "release_key": exercise.release_key,
        "release_at": exercise.release_at,
        "expires_at": exercise.expires_at,
        "source": exercise.source,
        "check_count": len(checks),
        "attempt_count": len(user_attempts),
        "best_percentage": round(max(percentages), 1) if percentages else None,
        "created_at": exercise.created_at,
    }


def practical_attempt_response(attempt: PracticalAttempt) -> dict:
    try:
        feedback = json.loads(attempt.feedback_json or "[]")
    except json.JSONDecodeError:
        feedback = []
    percentage = (attempt.score / attempt.total_points * 100) if attempt.total_points else 0
    return {
        "id": attempt.id,
        "exercise_id": attempt.exercise_id,
        "exercise_title": attempt.exercise.title,
        "course_id": attempt.exercise.course_id,
        "course_code": attempt.exercise.course.code if attempt.exercise.course else None,
        "practical_type": attempt.exercise.practical_type,
        "score": attempt.score,
        "total_points": attempt.total_points,
        "percentage": round(percentage, 2),
        "feedback": feedback,
        "solution_notes": attempt.exercise.solution_notes,
        "completed_at": attempt.completed_at,
    }
