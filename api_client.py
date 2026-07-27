import asyncio
import io
import zipfile
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
import zoneinfo

from config import HEADERS, BASE_URL
from db import DownloadedFile


async def fetch_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    while True:
        response = await client.request(method, url, **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"[429] Превышен лимит запросов. Ждем {retry_after} сек...")
            await asyncio.sleep(retry_after)
            continue
        
        response.raise_for_status()
        return response


async def run_download_pipeline(db: AsyncSession, download_state: dict):
    download_state["is_running"] = True
    download_state["started_at_nsk"] = datetime.now(
        zoneinfo.ZoneInfo("Asia/Novosibirsk")
    ).strftime("%Y-%m-%d %H:%M:%S (MSK+4)")
    download_state["total_discovered"] = 0
    download_state["total_downloaded"] = 0
    discovered_names = set()
    
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0) as client:
            while True:
                resp = await fetch_with_retry(client, "GET", "/api/files/names")
                filenames: list[str] = resp.json().get("file_names", [])

                if not filenames:
                    print("Все файлы успешно скачаны!")
                    break  

                discovered_names.update(filenames)
                download_state["total_discovered"] = len(discovered_names)
                
                chunk_size = 3
                batches = [filenames[i:i + chunk_size] for i in range(0, len(filenames), chunk_size)]
                
                for batch in batches:
                    dl_resp = await fetch_with_retry(
                        client, "POST", "/api/files/download", json={
                            "file_names": batch
                        }
                    )

                    with zipfile.ZipFile(io.BytesIO(dl_resp.content)) as z:
                        for name in z.namelist():
                            content = z.read(name).decode("utf-8")
                            downloaded_at = datetime.now(timezone.utc)
                            print(f"Скачан файл: {name}, символов: {len(content)}")
                            
                            new_recording = DownloadedFile(
                                filename=name,
                                content=content,
                                downloaded_at=downloaded_at
                            )
                            db.add(new_recording)
                            
                    await db.commit()
                            
                    await fetch_with_retry(
                        client, "POST", "/api/files/downloaded", json={
                            "file_names": batch
                        }
                    )
                    
                    download_state["total_downloaded"] += len(batch)
                    await asyncio.sleep(0.5) 
                    
    finally:
        download_state["is_running"] = False