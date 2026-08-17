import json

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, Response, stream_with_context
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Dataset, AIConversation, AIMessage
from app.utils.ownership import get_owned_or_404, owner_scoped_query
from app.utils.activity import log_activity
from app.services.analytics.dataset_processor import read_full_dataframe, DatasetProfilingError
from app.services.ai import get_provider_manager
from app.services.ai.analyst_service import ask_question, generate_insights, prepare_stream
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


def _resolve_conversation_and_question(dataset, body):
    """
    Shared by chat_ask() and chat_ask_stream(). Returns either
    (conversation, question, None) on success, or (None, None, (json, status))
    if validation failed and the route should return early.
    """
    question = (body.get("question") or "").strip()
    conversation_id = body.get("conversation_id")

    if not question:
        return None, None, ({"error": "Please enter a question."}, 400)
    if len(question) > 2000:
        return None, None, ({"error": "Question is too long."}, 400)

    if conversation_id:
        conversation = get_owned_or_404(AIConversation, conversation_id)
        if conversation.dataset_id != dataset.id:
            return None, None, ({"error": "Conversation does not belong to this dataset."}, 400)
    else:
        conversation = AIConversation(user_id=current_user.id, dataset_id=dataset.id, title=f"Chat about {dataset.name}")
        db.session.add(conversation)
        db.session.commit()

    return conversation, question, None


@ai_analyst_bp.route("/<int:dataset_id>/chat/ask", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def chat_ask(dataset_id):
    dataset, df, error = _load_dataset_and_df(dataset_id)
    if df is None:
        return jsonify({"error": error or "Could not read dataset."}), 400

    body = request.get_json(force=True, silent=True) or {}
    conversation, question, err = _resolve_conversation_and_question(dataset, body)
    if err:
        return jsonify(err[0]), err[1]

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


@ai_analyst_bp.route("/<int:dataset_id>/chat/ask/stream", methods=["POST"])
@login_required
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def chat_ask_stream(dataset_id):
    """
    Same grounded plan -> validate -> execute -> explain pipeline as
    chat_ask(), but the final explanation is streamed to the client as
    it's generated instead of returned as one blocking JSON response.

    The plan/validate/execute steps (fast — plain Pandas, not an AI call
    for the actual number) run synchronously up front, exactly like the
    blocking endpoint. Only the explanation call is streamed, via
    provider_manager.stream_analyze().

    conversation_id and computed_result can't ride inside a streamed text
    body without an envelope format, so they're sent as response headers
    before the body starts; the body itself is just the raw answer text.
    """
    dataset, df, error = _load_dataset_and_df(dataset_id)
    if df is None:
        return jsonify({"error": error or "Could not read dataset."}), 400

    body = request.get_json(force=True, silent=True) or {}
    conversation, question, err = _resolve_conversation_and_question(dataset, body)
    if err:
        return jsonify(err[0]), err[1]

    user_message = AIMessage(conversation_id=conversation.id, role="user", content=question)
    db.session.add(user_message)
    db.session.commit()

    manager = get_provider_manager(current_app)
    if not manager.configured_provider_order():
        return jsonify({"error": "No AI provider is configured yet. Add an API key in your environment settings."}), 503

    # Usage limit is checked here, proactively, before the streaming
    # response opens — stream() itself only checks lazily on first
    # iteration, which would be too late to cleanly return a 429 once
    # headers are already committed.
    try:
        manager.check_usage_limit(current_user.id)
    except UsageLimitExceededError as exc:
        return jsonify({"error": str(exc)}), 429

    try:
        planned = prepare_stream(manager, df, dataset.name, question, user_id=current_user.id)
    except UsageLimitExceededError as exc:
        return jsonify({"error": str(exc)}), 429

    conversation_id = conversation.id
    computed_result = planned["computed_result"]
    explain_context = planned["explain_context"]
    dataset_name = dataset.name

    def generate():
        collected = []
        try:
            for chunk in manager.stream_analyze(explain_context, question, user_id=current_user.id):
                collected.append(chunk)
                yield chunk
        except (AllProvidersExhaustedError, UsageLimitExceededError) as exc:
            error_note = f"\n\n[Response interrupted: {exc}]"
            collected.append(error_note)
            yield error_note
        finally:
            # stream_with_context() already keeps the original request/app
            # context alive for the lifetime of this generator — pushing
            # another one here would create a mismatched nested context
            # (confirmed by a real "popped wrong app context" failure
            # during testing). db.session is safe to use directly.
            full_text = "".join(collected)
            assistant_message = AIMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=full_text,
                computed_context_json=json.dumps(computed_result, default=str) if computed_result else None,
            )
            db.session.add(assistant_message)
            conv = db.session.get(AIConversation, conversation_id)
            if conv is not None:
                conv.title = conv.title or f"Chat about {dataset_name}"
            db.session.commit()
            log_activity(current_user.id, "ai_question_asked", f"dataset_id={dataset_id} conversation_id={conversation_id} streamed=true")

    response = Response(stream_with_context(generate()), mimetype="text/plain")
    response.headers["X-Conversation-Id"] = str(conversation_id)
    response.headers["X-Computed-Result"] = json.dumps(bool(computed_result))
    return response


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
