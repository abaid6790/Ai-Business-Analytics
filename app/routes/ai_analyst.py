import json

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Dataset, AIConversation, AIMessage
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.ai import get_provider_manager
from app.services.ai.analyst_service import ask_question, generate_insights
from app.services.ai.provider_manager import AllProvidersExhaustedError, UsageLimitExceededError

ai_analyst_bp = Blueprint("ai_analyst", __name__, template_folder="../templates/ai_analyst")


def _load_dataset_and_df(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)
    try:
        df = read_full_dataframe(dataset.file_path, dataset.file_type)
    except DatasetProfilingError as exc:
        return dataset, None, str(exc)
    return dataset, df, None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@ai_analyst_bp.route("/<int:dataset_id>/chat")
@login_required
def chat(dataset_id):
    dataset = get_owned_or_404(Dataset, dataset_id)

    conversation = (
        owner_scoped_query(AIConversation)
        .filter_by(dataset_id=dataset.id)
        .order_by(AIConversation.updated_at.desc())
        .first()
    )
    if conversation is None:
        conversation = AIConversation(user_id=current_user.id, dataset_id=dataset.id, title=f"Chat about {dataset.name}")
        db.session.add(conversation)
        db.session.commit()

    messages = conversation.messages.all()

    manager = get_provider_manager(current_app)
    ai_configured = bool(manager.configured_provider_order())

    return render_template(
        "ai_analyst/chat.html",
        dataset=dataset,
        conversation=conversation,
        messages=messages,
        ai_configured=ai_configured,
    )


@ai_analyst_bp.route("/<int:dataset_id>/chat/ask", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def chat_ask(dataset_id):
    dataset, df, error = _load_dataset_and_df(dataset_id)
    if df is None:
        return jsonify({"error": error or "Could not read dataset."}), 400

    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    conversation_id = body.get("conversation_id")

    if not question:
        return jsonify({"error": "Please enter a question."}), 400
    if len(question) > 2000:
        return jsonify({"error": "Question is too long."}), 400

    if conversation_id:
        conversation = get_owned_or_404(AIConversation, conversation_id)
        if conversation.dataset_id != dataset.id:
            return jsonify({"error": "Conversation does not belong to this dataset."}), 400
    else:
        conversation = AIConversation(user_id=current_user.id, dataset_id=dataset.id, title=f"Chat about {dataset.name}")
        db.session.add(conversation)
        db.session.commit()

    user_message = AIMessage(conversation_id=conversation.id, role="user", content=question)
    db.session.add(user_message)
    db.session.commit()

    manager = get_provider_manager(current_app)
    if not manager.configured_provider_order():
        return jsonify({"error": "No AI provider is configured yet. Add an API key in your environment settings."}), 503

    try:
        result = ask_question(manager, df, dataset.name, question, user_id=current_user.id)
    except UsageLimitExceededError as exc:
        return jsonify({"error": str(exc)}), 429
    except AllProvidersExhaustedError:
        return jsonify({"error": "All configured AI providers are currently unavailable. Please try again shortly."}), 503

    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        computed_context_json=json.dumps(result["computed_result"], default=str) if result["computed_result"] else None,
    )
    db.session.add(assistant_message)
    conversation.title = conversation.title or f"Chat about {dataset.name}"
    db.session.commit()

    log_activity(current_user.id, "ai_question_asked", f"dataset_id={dataset.id} conversation_id={conversation.id}")

    return jsonify({
        "conversation_id": conversation.id,
        "answer": result["answer"],
        "computed_result": result["computed_result"],
    })


@ai_analyst_bp.route("/conversations")
@login_required
def conversation_list():
    page = request.args.get("page", 1, type=int)
    pagination = (
        owner_scoped_query(AIConversation)
        .order_by(AIConversation.updated_at.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )
    return render_template("ai_analyst/conversation_list.html", pagination=pagination)


@ai_analyst_bp.route("/conversations/<int:conversation_id>/delete", methods=["POST"])
@login_required
def conversation_delete(conversation_id):
    conversation = get_owned_or_404(AIConversation, conversation_id)
    db.session.delete(conversation)
    db.session.commit()
    flash("Conversation deleted.", "info")
    return redirect(url_for("ai_analyst.conversation_list"))


# ---------------------------------------------------------------------------
# Automatic insights
# ---------------------------------------------------------------------------
@ai_analyst_bp.route("/<int:dataset_id>/insights")
@login_required
def insights(dataset_id):
    dataset, df, error = _load_dataset_and_df(dataset_id)
    if df is None:
        flash(f"Could not analyze this dataset: {error}", "danger")
        return redirect(url_for("datasets.detail", dataset_id=dataset_id))

    manager = get_provider_manager(current_app)
    ai_configured = bool(manager.configured_provider_order())

    return render_template("ai_analyst/insights.html", dataset=dataset, ai_configured=ai_configured)


@ai_analyst_bp.route("/<int:dataset_id>/insights/generate", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def insights_generate(dataset_id):
    dataset, df, error = _load_dataset_and_df(dataset_id)
    if df is None:
        return jsonify({"error": error or "Could not read dataset."}), 400

    manager = get_provider_manager(current_app)
    if not manager.configured_provider_order():
        return jsonify({"error": "No AI provider is configured yet."}), 503

    try:
        result = generate_insights(manager, df, dataset.name, user_id=current_user.id)
    except UsageLimitExceededError as exc:
        return jsonify({"error": str(exc)}), 429
    except AllProvidersExhaustedError:
        return jsonify({"error": "All configured AI providers are currently unavailable."}), 503

    # Persist as a conversation so it shows up in "recent AI questions" /
    # is available to the report generator later (Phase 12), without a
    # separate Insight model.
    conversation = AIConversation(
        user_id=current_user.id, dataset_id=dataset.id, title=f"Automatic insights: {dataset.name}"
    )
    db.session.add(conversation)
    db.session.commit()

    message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["insights_text"],
        computed_context_json=json.dumps(result["facts"], default=str),
    )
    db.session.add(message)
    db.session.commit()

    log_activity(current_user.id, "ai_insights_generated", f"dataset_id={dataset.id}")

    return jsonify({"insights_text": result["insights_text"], "facts": result["facts"]})
