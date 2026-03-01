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


def send_access_email(
    to_email: str,
    name: str,
    plan_name: str,
    access_url: str,
) -> None:
    """Отправляет подписчику письмо с персональной ссылкой доступа."""
    if not config.smtp_user:
        logger.warning("SMTP не настроен — письмо подписчику не отправлено")
        return

    subject = f"Ваш доступ к сервису мониторинга теплоснабжения"
    body = (
        f"Здравствуйте, {name}!\n\n"
        f"Ваша подписка «{plan_name}» успешно активирована.\n\n"
        f"Ссылка для входа в сервис:\n{access_url}\n\n"
        f"Это персональная ссылка — не передавайте её третьим лицам.\n"
        f"Ссылка сохраняется в браузере, повторный вход происходит автоматически.\n\n"
        f"Если возникнут вопросы — напишите нам: {config.admin_email}\n\n"
        f"С уважением,\nКоманда stampim.shop"
    )

    msg = MIMEMultipart()
    msg["From"] = config.smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.sendmail(config.smtp_user, to_email, msg.as_string())
        logger.info("Письмо с доступом отправлено на %s", to_email)
    except Exception as exc:
        logger.error("Ошибка отправки письма подписчику: %s", exc)
