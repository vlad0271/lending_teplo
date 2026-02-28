import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app import config

logger = logging.getLogger(__name__)


def send_order_email(
    plan_name: str,
    name: str,
    phone: str,
    email: str,
    payment_id: str | None = None,
) -> None:
    """Отправляет уведомление о заказе/оплате администратору."""
    if not config.admin_email or not config.smtp_user:
        logger.warning("SMTP не настроен — email не отправлен")
        return

    subject = f"Новая заявка: {plan_name}"
    if payment_id:
        subject = f"Оплата подтверждена: {plan_name}"

    lines = [
        f"Тариф: {plan_name}",
        f"Имя: {name}",
        f"Телефон: {phone}",
        f"Email: {email}",
    ]
    if payment_id:
        lines.append(f"ID платежа ЮКасса: {payment_id}")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"] = config.smtp_user
    msg["To"] = config.admin_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.smtp_user, config.admin_email, msg.as_string())
        logger.info("Email отправлен на %s", config.admin_email)
    except Exception as exc:
        logger.error("Ошибка отправки email: %s", exc)
