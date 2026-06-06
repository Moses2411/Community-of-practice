from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import STATIC_DIR

router = APIRouter()


@router.get("/")
def app_home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "ABU Zaria Community of Practice Research Platform", "docs": "/docs"}


@router.get("/api/health")
def health_check():
    return {"status": "ok", "service": "cop-research-platform"}
