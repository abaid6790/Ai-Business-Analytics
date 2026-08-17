import io
import json

from app.models import AIConversation, AIMessage, Dataset
from app.services.ai.base_provider import ProviderResponse
from app.services.ai.analyst_service import prepare_stream
from app.services.ai.provider_manager import AllProvidersExhaustedError, UsageLimitExceededError
from tests.conftest import create_verified_user, login

SAMPLE_CSV = (
    b"region,revenue\n"
    b"north,100\nsouth,200\nnorth,150\nsouth,50\neast,300\n"
)


def _upload_sample_dataset(client, name="Stream Sample"):
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


class FakeStreamManager:
    def __init__(self, plan=None, chunks=None, raise_error=None, usage_limit_error=None):
        self._plan = plan or {"operation": "aggregate", "column": "revenue", "agg": "sum"}
        self._chunks = chunks if chunks is not None else ["Total ", "revenue ", "is ", "800", "."]
        self._raise_error = raise_error
        self._usage_limit_error = usage_limit_error

    def configured_provider_order(self):
        return ["fake"]

    def check_usage_limit(self, user_id):
        if self._usage_limit_error:
            raise self._usage_limit_error

    def generate_json(self, prompt, **kwargs):
        return ProviderResponse(text=json.dumps(self._plan), provider="fake", model="m", parsed=self._plan)

    def analyze(self, context, question, **kwargs):
        if self._raise_error:
            raise self._raise_error
        return ProviderResponse(text="".join(self._chunks), provider="fake", model="m")

    def stream_analyze(self, context, question, user_id=None, **kwargs):
        if self._raise_error:
            raise self._raise_error
        for chunk in self._chunks:
            yield chunk


def _inject_fake_manager(app, **kwargs):
    app.extensions["ai_provider_manager"] = FakeStreamManager(**kwargs)


def test_prepare_stream_returns_grounded_context():
    import pandas as pd

    manager = FakeStreamManager(plan={"operation": "aggregate", "column": "revenue", "agg": "sum"})
    df = pd.DataFrame({"revenue": [100, 200, 300]})

    result = prepare_stream(manager, df, "Sales", "total revenue?", user_id=1)

    assert result["computed_result"]["value"] == 600
    assert result["explain_context"]["computed_result"]["value"] == 600


def test_prepare_stream_falls_back_on_invalid_plan():
    import pandas as pd

    manager = FakeStreamManager(plan={"operation": "aggregate", "column": "not_a_real_column", "agg": "sum"})
    df = pd.DataFrame({"revenue": [100, 200, 300]})

    result = prepare_stream(manager, df, "Sales", "what is x?", user_id=1)

    assert result["computed_result"] is None
    assert "computed_result" not in result["explain_context"]


def test_stream_endpoint_returns_grounded_streamed_text(client, db, app):
    create_verified_user(db, email="streamuser@example.com", password="Password123")
    login(client, "streamuser@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, chunks=["Total ", "revenue ", "is ", "800", "."])

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "What is total revenue?"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    assert resp.get_data(as_text=True) == "Total revenue is 800."


def test_stream_endpoint_sets_conversation_id_header(client, db, app):
    create_verified_user(db, email="streamheader@example.com", password="Password123")
    login(client, "streamheader@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    conv_id = resp.headers.get("X-Conversation-Id")
    assert conv_id is not None
    resp.get_data()  # drain the stream for deterministic generator cleanup
    assert db.session.get(AIConversation, int(conv_id)) is not None


def test_stream_endpoint_persists_full_answer_and_computed_context(client, db, app):
    create_verified_user(db, email="streampersist@example.com", password="Password123")
    login(client, "streampersist@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, chunks=["north ", "leads ", "with ", "300", "."])

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "which region leads?"}),
        content_type="application/json",
    )
    full_text = resp.get_data(as_text=True)
    conv_id = int(resp.headers["X-Conversation-Id"])

    messages = AIMessage.query.filter_by(conversation_id=conv_id).order_by(AIMessage.created_at).all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "which region leads?"
    assert messages[1].role == "assistant"
    assert messages[1].content == full_text
    assert messages[1].computed_context_json is not None


def test_stream_endpoint_rejects_empty_question(client, db, app):
    create_verified_user(db, email="streamempty@example.com", password="Password123")
    login(client, "streamempty@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "   "}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_stream_endpoint_no_provider_configured_returns_503(client, db, app):
    create_verified_user(db, email="streamnoprov@example.com", password="Password123")
    login(client, "streamnoprov@example.com", "Password123")
    dataset = _upload_sample_dataset(client)

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 503


def test_stream_endpoint_usage_limit_returns_429_before_streaming(client, db, app):
    create_verified_user(db, email="streamlimit@example.com", password="Password123")
    login(client, "streamlimit@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, usage_limit_error=UsageLimitExceededError("Daily limit reached (10)."))

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 429
    assert resp.is_json
    assert "limit" in resp.get_json()["error"].lower()


def test_stream_endpoint_mid_stream_failure_appends_error_note(client, db, app):
    create_verified_user(db, email="streamfail@example.com", password="Password123")
    login(client, "streamfail@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app, raise_error=AllProvidersExhaustedError("all providers down"))

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "anything"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "interrupted" in body.lower()


def test_stream_endpoint_continues_existing_conversation(client, db, app):
    create_verified_user(db, email="streamcontinue@example.com", password="Password123")
    login(client, "streamcontinue@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    r1 = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "first question"}),
        content_type="application/json",
    )
    conv_id = int(r1.headers["X-Conversation-Id"])
    r1.get_data()  # force the streaming generator to fully drain before the next request

    r2 = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "second question", "conversation_id": conv_id}),
        content_type="application/json",
    )
    assert int(r2.headers["X-Conversation-Id"]) == conv_id
    r2.get_data()

    messages = AIMessage.query.filter_by(conversation_id=conv_id).all()
    assert len(messages) == 4


def test_stream_endpoint_isolation_across_users(client, db, app):
    create_verified_user(db, email="streamowner@example.com", password="Password123")
    login(client, "streamowner@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)
    client.get("/auth/logout")

    create_verified_user(db, email="streamintruder@example.com", password="Password123")
    login(client, "streamintruder@example.com", "Password123")

    resp = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "trying to access"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_stream_endpoint_mixes_with_blocking_endpoint_in_same_conversation(client, db, app):
    create_verified_user(db, email="streammix@example.com", password="Password123")
    login(client, "streammix@example.com", "Password123")
    dataset = _upload_sample_dataset(client)
    _inject_fake_manager(app)

    r1 = client.post(
        f"/ai/{dataset.id}/chat/ask",
        data=json.dumps({"question": "blocking first"}),
        content_type="application/json",
    )
    conv_id = r1.get_json()["conversation_id"]

    r2 = client.post(
        f"/ai/{dataset.id}/chat/ask/stream",
        data=json.dumps({"question": "streamed second", "conversation_id": conv_id}),
        content_type="application/json",
    )
    assert int(r2.headers["X-Conversation-Id"]) == conv_id
    r2.get_data()
    assert AIMessage.query.filter_by(conversation_id=conv_id).count() == 4
