import subprocess
import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

import httpx
import yookassa
from yookassa import Payment

from app import config
from app.email_utils import send_order_email, send_access_email

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent

try:
    _ver = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BASE).decode().strip()
except Exception:
    _ver = "0"

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# Инициализация ЮКасса
if config.yookassa_shop_id and config.yookassa_secret_key:
    yookassa.Configuration.account_id = config.yookassa_shop_id
    yookassa.Configuration.secret_key = config.yookassa_secret_key


@app.get("/api/nodes")
async def get_nodes():
    return config.nodes


@app.get("/promo/check")
async def promo_check(code: str = ""):
    code = code.strip().upper()
    if not code:
        return JSONResponse({"valid": False, "message": "Введите промокод"})
    discount = config.promo_codes.get(code)
    if discount is None:
        return JSONResponse({"valid": False, "message": "Промокод не найден"})
    return JSONResponse({"valid": True, "discount_percent": discount,
                         "message": f"Скидка {discount}% применена"})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "contacts": config.settings["contacts"],
            "pain_points": config.settings["pain_points"],
            "plans": config.settings["plans"],
            "ver": _ver,
        },
    )


@app.post("/order")
async def order(
    plan_id: str = Form(...),
    plan_name: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(""),
    node_ids: str = Form(""),
    promo_code: str = Form(""),
):
    # Разбираем выбранные адреса
    selected_nodes = [n.strip() for n in node_ids.split(",") if n.strip()] if node_ids else []
    node_count = max(1, len(selected_nodes))

    logger.info(
        "[ORDER] plan=%s (%s), name=%s, phone=%s, email=%s, nodes=%s",
        plan_id, plan_name, name, phone, email, selected_nodes,
    )

    # Найти цену тарифа из настроек
    price = 0
    for plan in config.settings["plans"]:
        if plan["id"] == plan_id:
            price = plan.get("price_value", 0)
            break

    if price == 0:
        send_order_email(plan_name, name, phone, email)
        # Выдаём токен доступа если есть email и выбранный адрес
        if email and selected_nodes and config.heat_monitor_url and config.heat_monitor_api_key:
            current_month = datetime.now().strftime("%Y-%m")
            internal_headers = {"X-Internal-Key": config.heat_monitor_api_key}
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Проверяем лимит: не более 3 бесплатных токенов в месяц
                    count_resp = await client.get(
                        f"{config.heat_monitor_url}/internal/free-token-count",
                        params={"email": email, "month": current_month},
                        headers=internal_headers,
                    )
                    count_resp.raise_for_status()
                    if count_resp.json().get("count", 0) >= 3:
                        return JSONResponse({
                            "ok": False,
                            "message": "Лимит бесплатных запросов на этот месяц исчерпан (3 из 3). Попробуйте в следующем месяце.",
                        })
                    # Отзываем старые бесплатные токены этого email
                    await client.post(
                        f"{config.heat_monitor_url}/internal/revoke-by-email",
                        json={"email": email},
                        headers=internal_headers,
                    )
                    # Выдаём новый токен
                    token = str(uuid.uuid4())
                    access_url = f"{config.heat_monitor_url}?token={token}"
                    resp = await client.post(
                        f"{config.heat_monitor_url}/internal/add-token",
                        json={"token": token, "email": email, "plan_id": plan_id, "days": 30,
                              "node_ids": ",".join(selected_nodes), "is_free": True},
                        headers=internal_headers,
                    )
                    resp.raise_for_status()
                send_access_email(to_email=email, name=name, plan_name=plan_name, access_url=access_url)
                logger.info("Бесплатный токен выдан для %s, узлы: %s", email, selected_nodes)
                return JSONResponse({"ok": True, "message": "Доступ открыт! Ссылка отправлена на ваш email."})
            except Exception as exc:
                logger.error("Ошибка выдачи токена для бесплатного тарифа: %s", exc)
        return JSONResponse({"ok": True, "message": "Заявка принята! Мы свяжемся с вами."})

    # Платный тариф — создаём платёж ЮКасса
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        logger.error("ЮКасса не настроена — YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY отсутствуют")
        return JSONResponse(
            {"ok": False, "message": "Оплата временно недоступна. Попробуйте позже."},
            status_code=503,
        )

    # Нормализуем телефон в E.164 (+7XXXXXXXXXX) для ЮКасса
    phone_digits = "".join(c for c in phone if c.isdigit())
    if phone_digits.startswith("8") and len(phone_digits) == 11:
        phone_digits = "7" + phone_digits[1:]
    phone_e164 = "+" + phone_digits if phone_digits else phone

    customer = {"phone": phone_e164}
    if email:
        customer["email"] = email

    total_price = price * node_count

    # Применяем промокод
    discount_percent = 0
    promo_code = promo_code.strip().upper()
    if promo_code:
        discount_percent = config.promo_codes.get(promo_code, 0)
        if discount_percent:
            total_price = round(total_price * (100 - discount_percent) / 100, 2)
            logger.info("[PROMO] code=%s discount=%s%% total=%s", promo_code, discount_percent, total_price)

    # Цена единицы для чека — сумма позиций должна совпадать с total_price
    unit_price = round(total_price / node_count, 2) if node_count else total_price

    try:
        payment = Payment.create(
            {
                "amount": {"value": f"{total_price:.2f}", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{config.site_url}/payment/success",
                },
                "capture": True,
                "description": f"Подписка «{plan_name}» × {node_count} адр. — {name}"
                               + (f" (промокод {promo_code} -{discount_percent}%)" if discount_percent else ""),
                "receipt": {
                    "customer": customer,
                    "items": [
                        {
                            "description": f"Подписка «{plan_name}»",
                            "quantity": str(node_count),
                            "amount": {"value": f"{unit_price:.2f}", "currency": "RUB"},
                            "vat_code": 7,
                            "payment_mode": "full_payment",
                            "payment_subject": "service",
                        }
                    ],
                },
                "metadata": {
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "customer_name": name,
                    "customer_phone": phone,
                    "customer_email": email,
                    "node_ids": ",".join(selected_nodes),
                    "node_count": str(node_count),
                    "promo_code": promo_code,
                    "discount_percent": str(discount_percent),
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
    customer_email = meta.get("customer_email", "")
    customer_name = meta.get("customer_name", "")
    plan_name = meta.get("plan_name", "")
    plan_id = meta.get("plan_id", "")

    send_order_email(
        plan_name=plan_name,
        name=customer_name,
        phone=meta.get("customer_phone", ""),
        email=customer_email,
        payment_id=payment_id,
    )

    # Выдать токен доступа к stampim.space
    if customer_email and config.heat_monitor_url and config.heat_monitor_api_key:
        token = str(uuid.uuid4())
        access_url = f"{config.heat_monitor_url}?token={token}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{config.heat_monitor_url}/internal/add-token",
                    json={"token": token, "email": customer_email, "plan_id": plan_id, "days": 30,
                          "node_ids": meta.get("node_ids", "")},
                    headers={"X-Internal-Key": config.heat_monitor_api_key},
                )
                resp.raise_for_status()
            send_access_email(
                to_email=customer_email,
                name=customer_name,
                plan_name=plan_name,
                access_url=access_url,
            )
            logger.info("Токен доступа выдан для %s", customer_email)
        except Exception as exc:
            logger.error("Ошибка выдачи токена доступа для %s: %s", customer_email, exc)

    return JSONResponse({"ok": True})
