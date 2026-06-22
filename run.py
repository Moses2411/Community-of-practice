import os
import multiprocessing

PORT = int(os.environ.get("PORT", "8000"))
WORKERS = int(os.environ.get("WEB_CONCURRENCY", "1"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        workers=WORKERS,
    )
