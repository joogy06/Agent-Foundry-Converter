"""tests/test_crypto.py"""
import pytest

from transfer_kit.core.crypto import FernetEncryptor


def test_fernet_encrypt_decrypt_roundtrip():
    enc = FernetEncryptor()
    plaintext = b'GEMINI_API_KEY="secret123"\nOTHER_KEY="val"'
    passphrase = "test-passphrase"
    ciphertext = enc.encrypt(plaintext, passphrase)
    assert ciphertext != plaintext
    result = enc.decrypt(ciphertext, passphrase)
    assert result == plaintext


def test_fernet_wrong_passphrase_fails():
    enc = FernetEncryptor()
    ciphertext = enc.encrypt(b"secret", "correct")
    with pytest.raises(Exception):
        enc.decrypt(ciphertext, "wrong")


def test_fernet_different_salt_each_time():
    enc = FernetEncryptor()
    ct1 = enc.encrypt(b"same", "pass")
    ct2 = enc.encrypt(b"same", "pass")
    assert ct1 != ct2
