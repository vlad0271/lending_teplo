import uuid
import logging

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

import yookassa
from yookassa import Payment

from app import config
from app.email_utils import send_order_email

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# Инициализация ЮКасса
if config.yookassa_shop_id and config.yookassa_secret_key:
    yookassa.Configuration.account_id = config.yookassa_shop_id
    yookassa.Configuration.secret_key = config.yookassa_secret_key


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "contacts": config.settings["contacts"],
            "pain_points": config.settings["pain_points"],
            "plans": config.settings["plans"],
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
    logger.info(
        "[ORDER] plan=%s (%s), name=%s, phone=%s, email=%s",
        plan_id, plan_name, name, phone, email,
    )

    # Найти цену тарифа из настроек
    price = 0
    for plan in config.settings["plans"]:
        if plan["id"] == plan_id:
            price = plan.get("price_value", 0)
            break

    if price == 0:
        # Бесплатный тариф — только собираем контакты
        send_order_email(plan_name, name, phone, email)
        return JSONResponse({"ok": True, "message": "Заявка принята! Мы свяжемся с вами."})

    # Платный тариф — создаём платёж ЮКасса
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        logger.error("ЮКасса не настроена — YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY отсутствуют")
        return JSONResponse(
            {"ok": False, "message": "Оплата временно недоступна. Попробуйте позже."},
            status_code=503,
        )

    try:
        payment = Payment.create(
            {
                "amount": {"value": f"{price:.2f}", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{config.site_url}/payment/success",
                },
                "capture": True,
                "description": f"Подписка «{plan_name}» — {name}",
                "metadata": {
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "customer_name": name,
                    "customer_phone": phone,
                    "customer_email": email,
                },
            },
            str(uuid.uuid4()),
        )
        redirect_url = payment.confirmation.confirmation_url
        return JSONResponse({"redirect_url": redirect_url})
    except Exception as exc:
        logger.error("Ошибка создания платежа ЮКасса: %s", exc)
        return JSONResponse(
            {"ok": False, "message": "Ошибка при создании платежа. Попробуйте позже."},
            status_code=502,
        )


@app.get("/offer", response_class=HTMLResponse)
async def offer(request: Request):
    return templates.TemplateResponse(
        "offer.html",
        {
            "request": request,
            "contacts": config.settings["contacts"],
        },
    )


@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success(request: Request):
    return templates.TemplateResponse(
        "payment_result.html",
        {
            "request": request,
            "success": True,
            "message": "Оплата прошла успешно! Доступ к сервису будет открыт в течение нескольких минут.",
        },
    )


@app.get("/payment/fail", response_class=HTMLResponse)
async def payment_fail(request: Request):
    return templates.TemplateResponse(
        "payment_result.html",
        {
            "request": request,
            "success": False,
            "message": "Оплата не была завершена. Попробуйте ещё раз или выберите другой способ оплаты.",
        },
    )


@app.post("/payment/callback")
async def payment_callback(request: Request):
    """Webhook-уведомление от ЮКасса."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    event = body.get("event", "")
    obj = body.get("object", {})
    payment_id = obj.get("id", "")

    if event != "payment.succeeded" or not payment_id:
        # Игнорируем прочие события
        return JSONResponse({"ok": True})

    # Перепроверяем статус платежа через API
    try:
        payment = Payment.find_one(payment_id)
    except Exception as exc:
        logger.error("Ошибка получения платежа %s: %s", payment_id, exc)
        return JSONResponse({"ok": False}, status_code=502)

    if payment.status != "succeeded":
        return JSONResponse({"ok": True})

    meta = payment.metadata or {}
    send_order_email(
        plan_name=meta.get("plan_name", ""),
        name=meta.get("customer_name", ""),
        phone=meta.get("customer_phone", ""),
        email=meta.get("customer_email", ""),
        payment_id=payment_id,
    )

    return JSONResponse({"ok": True})
