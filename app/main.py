from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import settings

BASE = Path(__file__).parent.parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "contacts": settings["contacts"],
            "pain_points": settings["pain_points"],
            "plans": settings["plans"],
        },
    )


@app.post("/order")
async def order(
    plan_id: str = Form(...),
    plan_name: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(""),
):
    # В реальном проекте здесь сохранение в БД / отправка письма
    print(f"[ORDER] plan={plan_id} ({plan_name}), name={name}, phone={phone}, email={email}")
    return JSONResponse({"ok": True, "message": "Заявка принята! Мы свяжемся с вами."})
