from app.models import (
    User,
    Dataset,
    AnalysisProject,
    Chart,
    AIConversation,
    AIMessage,
    AIUsage,
    MLModel,
    Report,
    ActivityLog,
    EmailVerification,
    PasswordResetToken,
)


def test_password_hashing_never_stores_plaintext(db):
    user = User(email="a@example.com", full_name="A")
    user.set_password("SuperSecret123")
    db.session.add(user)
    db.session.commit()

    assert user.password_hash != "SuperSecret123"
    assert user.check_password("SuperSecret123") is True
    assert user.check_password("WrongPassword") is False


def test_user_creation_defaults(db):
    user = User(email="b@example.com", full_name="B")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()

    assert user.is_email_verified is False
    assert user.is_active_account is True
    assert user.is_admin is False
    assert user.created_at is not None


def test_dataset_belongs_to_user_and_project(db):
    user = User(email="c@example.com", full_name="C")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()

    project = AnalysisProject(user_id=user.id, name="Q1 Sales")
    db.session.add(project)
    db.session.commit()

    dataset = Dataset(
        user_id=user.id,
        project_id=project.id,
        name="sales.csv",
        file_path="/tmp/sales.csv",
        original_filename="sales.csv",
        file_type="csv",
        file_size_bytes=1024,
    )
    db.session.add(dataset)
    db.session.commit()

    assert dataset.owner.email == "c@example.com"
    assert dataset.project.name == "Q1 Sales"
    assert project.datasets.count() == 1


def test_dataset_cleaned_copy_lineage(db):
    user = User(email="d@example.com", full_name="D")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()

    original = Dataset(
        user_id=user.id,
        name="raw.csv",
        file_path="/tmp/raw.csv",
        original_filename="raw.csv",
        file_type="csv",
        file_size_bytes=500,
    )
    db.session.add(original)
    db.session.commit()

    cleaned = Dataset(
        user_id=user.id,
        name="raw_cleaned.csv",
        file_path="/tmp/raw_cleaned.csv",
        original_filename="raw.csv",
        file_type="csv",
        file_size_bytes=480,
        source_dataset_id=original.id,
        is_cleaned_copy=True,
    )
    db.session.add(cleaned)
    db.session.commit()

    assert cleaned.source_dataset.id == original.id
    assert cleaned.is_cleaned_copy is True
    assert original.is_cleaned_copy is False


def test_ai_conversation_and_messages_relationship(db):
    user = User(email="e@example.com", full_name="E")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()

    conversation = AIConversation(user_id=user.id, title="Sales Q&A")
    db.session.add(conversation)
    db.session.commit()

    msg1 = AIMessage(conversation_id=conversation.id, role="user", content="What are total sales?")
    msg2 = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="Total sales are $12,000.",
        computed_context_json='{"total_sales": 12000}',
    )
    db.session.add_all([msg1, msg2])
    db.session.commit()

    assert conversation.messages.count() == 2
    assert conversation.messages.first().role == "user"


def test_cascade_delete_user_removes_owned_data(db):
    user = User(email="f@example.com", full_name="F")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()
    user_id = user.id

    dataset = Dataset(
        user_id=user.id,
        name="d.csv",
        file_path="/tmp/d.csv",
        original_filename="d.csv",
        file_type="csv",
        file_size_bytes=10,
    )
    project = AnalysisProject(user_id=user.id, name="P")
    conversation = AIConversation(user_id=user.id, title="C")
    usage = AIUsage(user_id=user.id, provider="gemini", model="gemini-1.5-flash")
    activity = ActivityLog(user_id=user.id, action="login")

    db.session.add_all([dataset, project, conversation, usage, activity])
    db.session.commit()

    chart = Chart(
        user_id=user.id, dataset_id=dataset.id, title="Chart 1",
        chart_type="bar", config_json="{}",
    )
    ml_model = MLModel(
        user_id=user.id, dataset_id=dataset.id, name="Model 1",
        task_type="classification", algorithm="RandomForestClassifier",
        target_column="churn",
    )
    report = Report(user_id=user.id, title="Report 1", format="pdf", file_path="/tmp/r.pdf")
    db.session.add_all([chart, ml_model, report])
    db.session.commit()

    db.session.delete(user)
    db.session.commit()

    assert Dataset.query.filter_by(user_id=user_id).count() == 0
    assert AnalysisProject.query.filter_by(user_id=user_id).count() == 0
    assert AIConversation.query.filter_by(user_id=user_id).count() == 0
    assert AIUsage.query.filter_by(user_id=user_id).count() == 0
    assert ActivityLog.query.filter_by(user_id=user_id).count() == 0
    assert Chart.query.filter_by(user_id=user_id).count() == 0
    assert MLModel.query.filter_by(user_id=user_id).count() == 0
    assert Report.query.filter_by(user_id=user_id).count() == 0


def test_email_verification_and_password_reset_token_lifecycle(db):
    user = User(email="g@example.com", full_name="G")
    user.set_password("Password123")
    db.session.add(user)
    db.session.commit()

    ev = EmailVerification(user_id=user.id, token="tok-123")
    prt = PasswordResetToken(user_id=user.id, token="tok-456")
    db.session.add_all([ev, prt])
    db.session.commit()

    assert ev.is_used is False
    assert prt.is_used is False

    from datetime import datetime, timezone
    ev.used_at = datetime.now(timezone.utc)
    db.session.commit()
    assert ev.is_used is True
