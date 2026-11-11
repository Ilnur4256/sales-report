"""Отправка готового отчёта: e-mail (SMTP) и Telegram (Bot API sendDocument)."""

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import httpx


def build_email(
    *, sender: str, recipients: list[str], subject: str, body: str, attachment: Path
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    ctype = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    msg.add_attachment(
        attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name
    )
    return msg


def send_email(msg: EmailMessage, host: str, port: int, user: str, password: str) -> None:
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


def send_telegram(
    token: str, chat_id: str, file: Path, caption: str, client: httpx.Client | None = None
) -> None:
    client = client or httpx.Client(timeout=60)
    with file.open("rb") as f:
        r = client.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (file.name, f)},
        )
    r.raise_for_status()
