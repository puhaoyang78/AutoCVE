import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "secret",
    [
        "changethis_in_production_to_a_long_random_string",
        "your-super-secret-key-change-this-in-production",
    ],
)
def test_settings_rejects_known_insecure_secret_placeholders(secret):
    with pytest.raises(ValidationError, match="insecure placeholder"):
        Settings(SECRET_KEY=secret)
