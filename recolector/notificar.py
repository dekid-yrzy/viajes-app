"""Envío del resumen de alertas por Telegram y email (Gmail con contraseña de aplicación)."""
import smtplib
from email.message import EmailMessage

from recolector.red import ErrorRed


def telegram(texto: str, token: str, chat_id: str, post_json) -> None:
    resp = post_json(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat_id, "text": texto, "disable_web_page_preview": True})
    if not (resp or {}).get("ok"):
        raise RuntimeError("Telegram respondió ok=false")


def email(asunto: str, texto: str, usuario: str, clave: str, destino: str, smtp_factory=smtplib.SMTP_SSL) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = asunto, usuario, destino
    msg.set_content(texto)
    with smtp_factory("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(usuario, clave)
        smtp.send_message(msg)


def _resumen_error(e: Exception) -> str:
    # nunca str(e): la URL de Telegram lleva el token y los errores SMTP pueden repetir credenciales
    if isinstance(e, ErrorRed) and e.estado:
        return f"HTTP {e.estado}"
    return type(e).__name__


def enviar(texto: str, asunto: str, entorno: dict, post_json, smtp_factory=smtplib.SMTP_SSL) -> dict[str, dict]:
    estado = {}
    token, chat_id = entorno.get("TELEGRAM_BOT_TOKEN"), entorno.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            telegram(texto, token, chat_id, post_json)
            estado["telegram"] = {"estado": "ok", "detalle": ""}
        except Exception as e:
            estado["telegram"] = {"estado": "error", "detalle": _resumen_error(e)}
    else:
        estado["telegram"] = {"estado": "sin_configurar", "detalle": ""}
    usuario, clave, destino = entorno.get("SMTP_USER"), entorno.get("SMTP_PASSWORD"), entorno.get("EMAIL_DESTINO")
    if usuario and clave and destino:
        try:
            email(asunto, texto, usuario, clave, destino, smtp_factory)
            estado["email"] = {"estado": "ok", "detalle": ""}
        except Exception as e:
            estado["email"] = {"estado": "error", "detalle": _resumen_error(e)}
    else:
        estado["email"] = {"estado": "sin_configurar", "detalle": ""}
    return estado
