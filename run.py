import os

PORT = int(os.environ.get("PORT", "8000"))
WORKERS = int(os.environ.get("WEB_CONCURRENCY", "1"))

if __name__ == "__main__":
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect
    from pathlib import Path

    from app.practical_schedule import ensure_practical_release_schema
    from app.seed import seed_database
    from db.database import Base, SessionLocal, engine

    alembic_cfg = Config(Path(__file__).resolve().parent / "alembic.ini")
    inspector = inspect(engine)

    if "alembic_version" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")

    ensure_practical_release_schema()
    with SessionLocal() as db:
        seed_database(db)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        workers=WORKERS,
    )
