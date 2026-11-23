import pytest
from pydantic import ValidationError

from app.schemas import AskRequest, UserCreate

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("question", ["What is the late fee?", "abc", "x" * 1000])
def test_valid_questions_accepted(question):
    assert AskRequest(question=question).question == question


@pytest.mark.parametrize("question", ["", "hi", "x" * 1001])
def test_too_short_or_too_long_rejected(question):
    with pytest.raises(ValidationError):
        AskRequest(question=question)


def test_question_is_required():
    with pytest.raises(ValidationError):
        AskRequest()


def test_question_must_be_text():
    with pytest.raises(ValidationError):
        AskRequest(question=["not", "a", "string"])


def test_bad_email_rejected():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="longenough", full_name="A")


def test_short_password_rejected():
    with pytest.raises(ValidationError):
        UserCreate(email="a@uni.edu", password="short", full_name="A")


def test_role_defaults_to_student():
    user = UserCreate(email="a@uni.edu", password="longenough", full_name="A")
    assert user.role == "student"


def test_any_role_string_is_accepted_today():
    # FINDING (also flagged in the app's own code): self-registration can pick any role.
    user = UserCreate(email="a@uni.edu", password="longenough", full_name="A", role="admin")
    assert user.role == "admin"