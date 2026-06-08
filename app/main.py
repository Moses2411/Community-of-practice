from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import STATIC_DIR
from app.pages import router as pages_router
from app.routers import (
    academic,
    activity,
    auth,
    courses,
    discussions,
    feedback,
    instructor,
    notifications,
    quizzes,
    reflections,
    research,
    resources,
    surveys,
)
from app.seed import reset_stale_sqlite_schema, seed_database
from db.database import Base, SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_stale_sqlite_schema()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(
    title="ABU Zaria Community of Practice Research Platform",
    version="2.0.0",
    description="A FastAPI edTech platform for learning engagement, academic performance, and community of practice research.",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages_router)
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(resources.router)
app.include_router(surveys.router)
app.include_router(discussions.router)
app.include_router(quizzes.router)
app.include_router(reflections.router)
app.include_router(feedback.router)
app.include_router(activity.router)
app.include_router(academic.router)
app.include_router(research.router)
app.include_router(instructor.router)
app.include_router(notifications.router)
