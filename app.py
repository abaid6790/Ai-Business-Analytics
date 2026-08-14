from app import create_app
from app.extensions import db

app = create_app()


@app.shell_context_processor
def make_shell_context():
    from app.models import (
        User,
        EmailVerification,
        PasswordResetToken,
        Dataset,
        AnalysisProject,
        Chart,
        AIConversation,
        AIMessage,
        AIUsage,
        MLModel,
        Report,
        ActivityLog,
    )

    return {
        "db": db,
        "User": User,
        "EmailVerification": EmailVerification,
        "PasswordResetToken": PasswordResetToken,
        "Dataset": Dataset,
        "AnalysisProject": AnalysisProject,
        "Chart": Chart,
        "AIConversation": AIConversation,
        "AIMessage": AIMessage,
        "AIUsage": AIUsage,
        "MLModel": MLModel,
        "Report": Report,
        "ActivityLog": ActivityLog,
    }


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
