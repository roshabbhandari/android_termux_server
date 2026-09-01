from app.security import hash_password, verify_password

def test_password_roundtrip():
    encoded = hash_password("a-long-test-password-123")
    assert verify_password("a-long-test-password-123", encoded)
    assert not verify_password("wrong-password", encoded)
