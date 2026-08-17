"""
Registers `flask create-admin` — bootstraps the first admin account from
ADMIN_EMAIL / ADMIN_PASSWORD (spec section 20's .env.example already
reserves these). Safe to run repeatedly: promotes an existing user to
admin if the email is already registered, otherwise creates a new
pre-verified admin account.
"""

import click
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User


@click.command("create-admin")
@with_appcontext
def create_admin_command():
    email = current_app.config.get("ADMIN_EMAIL")
    password = current_app.config.get("ADMIN_PASSWORD")

    if not email or not password:
        click.echo("ADMIN_EMAIL and ADMIN_PASSWORD must be set in your environment.")
        return

    user = User.query.filter_by(email=email.lower().strip()).first()

    if user is None:
        user = User(email=email.lower().strip(), full_name="Administrator", is_email_verified=True, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin account: {email}")
    else:
        user.is_admin = True
        user.is_email_verified = True
        db.session.commit()
        click.echo(f"Promoted existing user to admin: {email}")


@click.command("cleanup-temp-uploads")
@with_appcontext
def cleanup_temp_uploads_command():
    from app.services.analytics.storage import cleanup_stale_temp_uploads

    deleted = cleanup_stale_temp_uploads(
        upload_folder=current_app.config["UPLOAD_FOLDER"],
        temp_subfolder=current_app.config["DATASET_TEMP_SUBFOLDER"],
        max_age_hours=current_app.config["DATASET_TEMP_MAX_AGE_HOURS"],
    )
    click.echo(f"Deleted {deleted} stale temp upload(s).")


def register_cli(app):
    app.cli.add_command(create_admin_command)
    app.cli.add_command(cleanup_temp_uploads_command)
