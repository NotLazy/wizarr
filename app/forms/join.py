from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Optional, Email, EqualTo, Length, Regexp, ValidationError


class JoinForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired()],
    )
    # email = StringField(
    #     "Email (optional)",
    #     validators=[Optional(), Email()],
    # )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
                message="Password must contain at least one uppercase letter, one lowercase letter, and one number.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    code = StringField(
        "Invite Code",
        validators=[DataRequired(), Length(min=6, max=10)],
        render_kw={"minlength": 6, "maxlength": 10},
    )

    def validate_username(self, field):
        """Custom validation for username against invitation requirements."""
        from app.models import Invitation
        from sqlalchemy import func
        
        # Get the invitation code from the form
        code = self.code.data
        if code:
            invitation = Invitation.query.filter(
                func.lower(Invitation.code) == code.lower()
            ).first()
            
            if invitation and invitation.required_username:
                if field.data != invitation.required_username:
                    raise ValidationError(f"Username must be exactly '{invitation.required_username}' for this invitation.")
