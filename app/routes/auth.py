from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter
from app.models import User, EmailVerification, PasswordResetToken
from app.forms.auth_forms import (
    RegisterForm,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    ChangePasswordForm,
    ProfileForm,
    DeleteAccountForm,
    ResendVerificationForm,
)
from app.utils.tokens import generate_token, verify_token
from app.utils.email import send_email
from app.utils.activity import log_activity

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["AUTH_RATE_LIMIT"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(),
            full_name=form.full_name.data.strip(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        _send_verification_email(user)
        log_activity(user.id, "register", f"email={user.email}")

        flash("Account created. Please check your email to verify your address.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
def _send_verification_email(user: User) -> None:
    token = generate_token(user.email, "EMAIL_VERIFICATION_SALT")
    record = EmailVerification(user_id=user.id, token=token)
    db.session.add(record)
    db.session.commit()

    verify_url = url_for("auth.verify_email", token=token, _external=True)
    send_email(
        subject="Verify your email address",
        recipients=[user.email],
        template_prefix="email/verify_email",
        user=user,
        verify_url=verify_url,
    )


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    email = verify_token(token, "EMAIL_VERIFICATION_SALT", "EMAIL_TOKEN_MAX_AGE_SECONDS")
    record = EmailVerification.query.filter_by(token=token).first()

    if email is None or record is None:
        flash("That verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.resend_verification"))

    if record.is_used:
        flash("That verification link has already been used.", "info")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash("That verification link is invalid.", "danger")
        return redirect(url_for("auth.register"))

    user.is_email_verified = True
    record.used_at = datetime.now(timezone.utc)
    db.session.commit()

    log_activity(user.id, "email_verified")
    flash("Your email has been verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["AUTH_RATE_LIMIT"])
def resend_verification():
    form = ResendVerificationForm()
    if form.validate_on_submit():
        email = request.form.get("email", "").lower().strip()
        user = User.query.filter_by(email=email).first()
        # Always show the same message, regardless of whether the account
        # exists, to avoid leaking which emails are registered.
        if user and not user.is_email_verified:
            _send_verification_email(user)
        flash("If that account exists and is unverified, a new email has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/resend_verification.html", form=form)


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["AUTH_RATE_LIMIT"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("This account has been disabled. Contact support.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_email_verified:
            flash("Please verify your email before logging in.", "warning")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        log_activity(user.id, "login")

        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity(current_user.id, "logout")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["AUTH_RATE_LIMIT"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_token(user.email, "PASSWORD_RESET_SALT")
            record = PasswordResetToken(user_id=user.id, token=token)
            db.session.add(record)
            db.session.commit()

            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_email(
                subject="Reset your password",
                recipients=[user.email],
                template_prefix="email/reset_password",
                user=user,
                reset_url=reset_url,
            )
            log_activity(user.id, "password_reset_requested")

        # Same message whether or not the account exists.
        flash("If that account exists, a password reset email has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_token(token, "PASSWORD_RESET_SALT", "PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS")
    record = PasswordResetToken.query.filter_by(token=token).first()

    if email is None or record is None or record.is_used:
        flash("That password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        if user is None:
            flash("That password reset link is invalid.", "danger")
            return redirect(url_for("auth.forgot_password"))

        user.set_password(form.password.data)
        record.used_at = datetime.now(timezone.utc)
        db.session.commit()

        log_activity(user.id, "password_reset_completed")
        flash("Your password has been reset. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


# ---------------------------------------------------------------------------
# Profile / change password / delete account
# ---------------------------------------------------------------------------
@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        db.session.commit()
        log_activity(current_user.id, "profile_updated")
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        log_activity(current_user.id, "password_changed")
        flash("Your password has been changed.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password.data):
            flash("Incorrect password. Account not deleted.", "danger")
            return render_template("auth/delete_account.html", form=form)

        user_id = current_user.id
        user_email = current_user.email
        logout_user()

        user = db.session.get(User, user_id)
        db.session.delete(user)  # cascades to all owned data
        db.session.commit()

        current_app.logger.info("Account deleted: %s", user_email)
        flash("Your account and all associated data have been deleted.", "info")
        return redirect(url_for("main.index"))

    return render_template("auth/delete_account.html", form=form)
