from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length


class SaveChartForm(FlaskForm):
    title = StringField("Chart title", validators=[DataRequired(), Length(max=255)])
    chart_type = HiddenField(validators=[DataRequired()])
    config_json = HiddenField(validators=[DataRequired()])
    submit = SubmitField("Save chart")
