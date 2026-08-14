from flask import current_app, render_template
from flask_mail import Message

from app.extensions import mail


def send_email(subject: str, recipients: list[str], template_prefix: str, **context) -> None:
    """
    Renders `<template_prefix>.txt` and `<template_prefix>.html` from
    app/templates/email/ and sends via Flask-Mail.

    In dev (MAIL_SUPPRESS_SEND=True), Flask-Mail's suppress-send mode is used
    automatically by the app config — the message is logged instead of sent.
    """
    text_body = render_template(f"{template_prefix}.txt", **context)
    html_body = render_template(f"{template_prefix}.html", **context)

    msg = Message(
        subject=subject,
        recipients=recipients,
        body=text_body,
        html=html_body,
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )

    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info(
            "[EMAIL SUPPRESSED] to=%s subject=%s\n%s", recipients, subject, text_body
        )

    mail.send(msg)
