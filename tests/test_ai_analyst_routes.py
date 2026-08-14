import io
import json

import pytest

from app.models import Dataset, AIConversation, AIMessage
from app.services.ai.base_provider import ProviderResponse
from app.services.ai.provider_manager import AllProvidersExhaustedError, UsageLimitExceededError
from tests.conftest import create_verified_user, login

SAMPLE_CSV = (
    b"region,revenue,date\n"
    b"north,100,2024-01-01\n"
    b"south,200,2024-01-15\n"
    b"north,150,2024-02-01\n"
    b"south,50,2024-02-15\n"
    b"east,300,2024-03-01\n"
)


def _upload_sample_dataset(client, name="AI Sample"):
    data = {"file": (io.BytesIO(SAMPLE_CSV), "sample.csv")}
    resp = client.post("/datasets/upload/preview", data=data, content_type="multipart/form-data")
    body = resp.get_json()
    client.post(
        "/datasets/upload/commit",
        data={
            "name": name,
            "temp_filename": body["temp_filename"],
            "original_filename": body["original_filename"],
            "file_type": body["file_type"],
            "file_size_bytes": body["file_size_bytes"],
        },
        follow_redirects=True,
    )
    return Dataset.query.filter_by(name=name).first()


class FakeManager:
    """Injected in place of the real AIProviderManager via app.extensions,
    so route tests never touch the network."""

    def __init__(self, plan=None, answer_text="Grounded answer.", insights_text="- insight one",
                 raise_error=None):
        self._plan = plan or {"operation": "aggregate", "column": "revenue", "agg": "sum"}
        self._answer_text = answer_text
        self._insights_text = insights_text
        self._raise_error = raise_error

    def configured_provider_order(self):
        return ["fake"]

    def generate_json(self, prompt, **kwargs):
        if self._raise_error:
            raise self._raise_error
        return ProviderResponse(text=json.dumps(self._plan), provider="fake", model="m", parsed=self._plan)

    def generate(self, prompt, **kwargs):
        if self._raise_error:
            raise self._raise_error
        return ProviderResponse(text=self._insights_text, provider="fake", model="m")

    def analyze(self, context, question, **kwargs):
        if self._raise_error:
            raise self._raise_error
        return ProviderResponse(text=self._answer_text, provider="fake", model="m")


def _inject_fake_manager(app, **kwargs):
    app.extensions["ai_provider_manager"] = FakeManager(**kwargs)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def test_chat_page_loads_and_creates_conversation(client, db, app):
    create_verified_user(db, email="chatuser@example.com", password="Password123")
    login(client, "chatuser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    resp = client.get(f"/ai/{dataset.id}/chat")
    assert resp.status_code == 200

    conversation = AIConversation.query.filter_by(dataset_id=dataset.id).first()
    assert conversation is not None


def test_chat_ask_persists_messages_and_returns_grounded_answer(client, db, app):
    create_verified_user(db, email="chatask@example.com", password="Password123")
    login(client, "chatask@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, answer_text="Total revenue is 800.")

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "What is total revenue?"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["answer"] == "Total revenue is 800."
    assert body["computed_result"]["value"] == 800

    conversation_id = body["conversation_id"]
    messages = AIMessage.query.filter_by(conversation_id=conversation_id).order_by(AIMessage.created_at).all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is total revenue?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Total revenue is 800."
    assert messages[1].computed_context_json is not None


def test_chat_ask_rejects_empty_question(client, db, app):
    create_verified_user(db, email="emptyq@example.com", password="Password123")
    login(client, "emptyq@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "   "}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_chat_ask_no_provider_configured_returns_503(client, db, app):
    create_verified_user(db, email="noprovider@example.com", password="Password123")
    login(client, "noprovider@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    # Don't inject a fake manager — real one has zero configured providers in tests

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 503


def test_chat_ask_usage_limit_returns_429(client, db, app):
    create_verified_user(db, email="limituser@example.com", password="Password123")
    login(client, "limituser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, raise_error=UsageLimitExceededError("Daily limit reached (10)."))

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 429


def test_chat_ask_all_providers_exhausted_returns_503(client, db, app):
    create_verified_user(db, email="exhausted@example.com", password="Password123")
    login(client, "exhausted@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, raise_error=AllProvidersExhaustedError("all down"))

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 503


def test_chat_conversation_continues_with_same_id(client, db, app):
    create_verified_user(db, email="continuity@example.com", password="Password123")
    login(client, "continuity@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    r1 = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "first question"}),
        content_type="application/json",
    )
    conv_id = r1.get_json()["conversation_id"]

    r2 = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "second question", "conversation_id": conv_id}),
        content_type="application/json",
    )
    assert r2.get_json()["conversation_id"] == conv_id

    messages = AIMessage.query.filter_by(conversation_id=conv_id).all()
    assert len(messages) == 4  # 2 user + 2 assistant


def test_chat_isolation_across_users(client, db, app):
    create_verified_user(db, email="chatowner@example.com", password="Password123")
    login(client, "chatowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "private question"}),
        content_type="application/json",
    )
    client.get("/auth/logout")

    create_verified_user(db, email="chatintruder@example.com", password="Password123")
    login(client, "chatintruder@example.com", "Password123")

    resp = client.get(f"/ai/{dataset.id}/chat")
    assert resp.status_code == 404

    resp2 = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "trying to access"}),
        content_type="application/json",
    )
    assert resp2.status_code == 404


def test_conversation_list_shows_only_own_conversations(client, db, app):
    create_verified_user(db, email="listowner@example.com", password="Password123")
    login(client, "listowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "my question"}),
        content_type="application/json",
    )

    resp = client.get("/ai/conversations")
    assert resp.status_code == 200
    assert b"AI Sample" in resp.data


def test_conversation_delete_requires_ownership(client, db, app):
    create_verified_user(db, email="delowner@example.com", password="Password123")
    login(client, "delowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    r1 = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "q"}),
        content_type="application/json",
    )
    conv_id = r1.get_json()["conversation_id"]
    client.get("/auth/logout")

    create_verified_user(db, email="delintruder@example.com", password="Password123")
    login(client, "delintruder@example.com", "Password123")

    resp = client.post(f"/ai/conversations/{conv_id}/delete")
    assert resp.status_code == 404
    assert db.session.get(AIConversation, conv_id) is not None


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------
def test_insights_page_loads(client, db, app):
    create_verified_user(db, email="insightsuser@example.com", password="Password123")
    login(client, "insightsuser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    resp = client.get(f"/ai/{dataset.id}/insights")
    assert resp.status_code == 200


def test_insights_generate_persists_conversation(client, db, app):
    create_verified_user(db, email="insightsgen@example.com", password="Password123")
    login(client, "insightsgen@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, insights_text="- East region leads.")

    resp = client.post(f"/ai/{dataset.id}/insights/generate")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["insights_text"] == "- East region leads."
    assert len(body["facts"]) > 0

    conversation = AIConversation.query.filter_by(
        dataset_id=dataset.id, title=f"Automatic insights: {dataset.name}"
    ).first()
    assert conversation is not None
    message = conversation.messages.first()
    assert message.content == "- East region leads."
    assert message.computed_context_json is not None


def test_insights_isolation_across_users(client, db, app):
    create_verified_user(db, email="insightowner@example.com", password="Password123")
    login(client, "insightowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)
    client.get("/auth/logout")

    create_verified_user(db, email="insightintruder@example.com", password="Password123")
    login(client, "insightintruder@example.com", "Password123")

    resp = client.get(f"/ai/{dataset.id}/insights")
    assert resp.status_code == 404

    resp2 = client.post(f"/ai/{dataset.id}/insights/generate")
    assert resp2.status_code == 404
