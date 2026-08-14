from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class DatasetCommitForm(FlaskForm):
    """
    Submitted after the AJAX preview step. The file itself was already
    uploaded to temp storage — this form just carries the metadata plus a
    reference to that temp file.
    """
    name = StringField("Dataset name", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])

    temp_filename = HiddenField(validators=[DataRequired()])
    original_filename = HiddenField(validators=[DataRequired()])
    file_type = HiddenField(validators=[DataRequired()])
    file_size_bytes = HiddenField(validators=[DataRequired()])

    submit = SubmitField("Save dataset")


class DatasetEditForm(FlaskForm):
    name = StringField("Dataset name", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save changes")
