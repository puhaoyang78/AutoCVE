import bcrypt

from app.core.security import get_password_hash, verify_password


def test_password_hash_round_trip_uses_bcrypt_format():
    password = "correct horse battery staple"

    hashed = get_password_hash(password)

    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password(password, hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_verify_password_accepts_existing_bcrypt_hashes():
    password = "existing-password"
    existing_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    assert verify_password(password, existing_hash) is True


def test_verify_password_rejects_malformed_hash():
    assert verify_password("password", "not-a-bcrypt-hash") is False

