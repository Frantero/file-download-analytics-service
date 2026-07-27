from fastapi import FastAPI, Depends, BackgroundTasks, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select, desc, asc
from pydantic import BaseModel
from typing import List, Optional


from analytics import calculate_files_statistics
from api_client import run_download_pipeline
from db import init_db, get_db, DownloadedFile, AsyncSessionLocal

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request


class CalculateRequest(BaseModel):
    file_ids: Optional[List[int]] = None
    select_all: bool = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

    

app = FastAPI(lifespan=lifespan)


templates = Jinja2Templates(directory="templates")

download_state = {
    "is_running": False,
    "started_at_nsk": None,
    "total_discovered": 0,
    "total_downloaded": 0,
    "error": None
}

async def run_pipeline_with_session():
    async with AsyncSessionLocal() as db:
        await run_download_pipeline(db, download_state)

@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html"
    )

@app.get("/api/download/status")
async def get_download_status():
    return download_state


@app.post("/api/download/start")
async def start_download(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline_with_session)
    return {"status": "started", "message": "Процесс скачивания запущен в фоне"}


@app.get("/api/analytics/files")
async def get_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size
    sort_order = desc(DownloadedFile.downloaded_at) if order == "desc" else asc(DownloadedFile.downloaded_at)
    stmt = select(DownloadedFile).order_by(sort_order).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    files = result.scalars().all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "downloaded_at": f.downloaded_at
        }
        for f in files
    ]

@app.post("/api/analytics/calculate")
async def calculate_analytics(
    payload: CalculateRequest,
    db: AsyncSession = Depends(get_db)
):
    if payload.select_all:
        stmt = select(DownloadedFile)
    elif payload.file_ids:
        stmt = select(DownloadedFile).where(DownloadedFile.id.in_(payload.file_ids))
    else:
        raise HTTPException(
            status_code=400, 
            detail="Укажите file_ids или передайте select_all: true"
        )

    result = await db.execute(stmt)
    files = result.scalars().all()

    if not files:
        raise HTTPException(status_code=404, detail="Файлы не найдены")

    return calculate_files_statistics(files)


if __name__ == "__main__":
    import uvicorn 
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )