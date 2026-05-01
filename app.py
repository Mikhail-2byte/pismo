"""
FastAPI web application for the letter generator.
Run: python app.py  →  http://127.0.0.1:8000
"""

import os
import re
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from parser import parse_excel
from generator import generate_letter_stream
from filler import fill_template
from config import TEMPLATE_PATH, OUTPUT_DIR

app = FastAPI(title="Генератор деловых писем")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

SESSIONS: dict[str, dict] = {}

os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    if not (file.filename or '').endswith('.xlsx'):
        raise HTTPException(400, "Поддерживаются только файлы .xlsx")

    session_id = str(uuid.uuid4())
    tmp_path = os.path.join(OUTPUT_DIR, f"tmp_{session_id}.xlsx")

    try:
        content = await file.read()
        with open(tmp_path, 'wb') as f:
            f.write(content)
        data = parse_excel(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"Ошибка чтения файла: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    managers = list(data.keys())
    if not managers:
        raise HTTPException(400, "Менеджеры не найдены в файле")

    SESSIONS[session_id] = {'data': data}
    return {"session_id": session_id, "managers": managers}


@app.get("/api/contracts")
async def get_contracts_api(session_id: str, manager: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    manager_data = session['data'].get(manager, [])
    return {
        "contracts": [
            {"company": item["company"], "contract": item["contract"], "spec_count": len(item["specs"])}
            for item in manager_data
        ]
    }


@app.get("/api/specs")
async def get_specs_api(session_id: str, manager: str, contract_idx: int):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    contracts = session['data'].get(manager, [])
    if contract_idx >= len(contracts):
        raise HTTPException(404, "Договор не найден")

    c = contracts[contract_idx]
    return {"company": c["company"], "contract": c["contract"], "specs": c["specs"]}


def _sse_generator(entries, manager, comment, feedback, previous_text) -> Iterator[str]:
    try:
        for chunk in generate_letter_stream(entries, manager, comment, feedback, previous_text):
            if chunk:
                yield f"data: {json.dumps(chunk)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'__error__': str(e)})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/api/generate-stream")
async def generate_stream(request: Request):
    body = await request.json()
    return StreamingResponse(
        _sse_generator(
            body["entries"],
            body["manager"],
            body.get("comment", ""),
            body.get("feedback", ""),
            body.get("previous_text", ""),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/download")
async def download_docx(request: Request):
    body = await request.json()
    body_text = body["body_text"]
    company = body["company"]
    manager = body["manager"]
    specs_str = body.get("specs_str", "")

    today = datetime.now()

    def safe(s: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', '_', s)

    filename = f"letter_{safe(company)}_{safe(specs_str)}_{today.strftime('%Y-%m-%d')}.docx"
    output_path = os.path.join(OUTPUT_DIR, filename)

    fill_template(TEMPLATE_PATH, {
        "date": today.strftime("%d.%m.%Y"),
        "company": company,
        "contact_info": f"Менеджер: {manager}\nТел.: ___________",
        "body": body_text,
    }, output_path)

    encoded = quote(filename.encode('utf-8'), safe='')
    ascii_fallback = f"letter_{today.strftime('%Y-%m-%d')}.docx"
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
            ),
        },
    )


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 52)
    print("  Генератор деловых писем")
    print("  Откройте браузер: http://127.0.0.1:8000")
    print("=" * 52 + "\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
