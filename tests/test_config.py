"""Invalid bearer-token configuration is rejected before accepting requests."""

import pytest

from backend.config import Settings


@pytest.mark.parametrize("token", ["", " ", " leading", "trailing ", "two parts", "line\nbreak"])
def test_hr_token_rejects_empty_and_whitespace_values(token):
    with pytest.raises(ValueError, match="HR_API_TOKEN"):
        Settings(hr_token=token, runtime_state_path=None)


def test_hr_and_employee_credentials_cannot_share_one_token():
    with pytest.raises(ValueError, match="must be different"):
        Settings(hr_token="shared-token", employee_tokens={"shared-token": "person-alpha"}, runtime_state_path=None)
