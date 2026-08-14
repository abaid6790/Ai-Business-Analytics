"""
Reusable data-isolation guard.

Every route that loads a user-owned object (Dataset, Chart, MLModel, Report,
AIConversation, AnalysisProject, ...) MUST go through `get_owned_or_404`
rather than a raw `Model.query.get()`. This is the single choke point that
guarantees a user can never read/modify another user's data, satisfying
spec section 29 (data privacy) everywhere in one place instead of ad hoc
checks scattered across routes.
"""

from flask import abort
from flask_login import current_user


def get_owned_or_404(model, object_id, user_field="user_id"):
    """
    Fetch `model` by primary key, then verify it belongs to current_user.
    Returns the object or aborts with 404 (not 403, to avoid leaking
    existence of other users' records).
    """
    from app.extensions import db

    obj = db.session.get(model, object_id)
    if obj is None:
        abort(404)
    if getattr(obj, user_field) != current_user.id:
        abort(404)
    return obj


def owner_scoped_query(model, user_field="user_id"):
    """Returns a query pre-filtered to the current user's own rows."""
    return model.query.filter(getattr(model, user_field) == current_user.id)
