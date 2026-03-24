"""transfer_kit/core/crypto.py — Encryption for sync secrets."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class FernetEncryptor:
    """Fernet symmetric encryption with PBKDF2 key derivation."""

    ITERATIONS = 600_000
    SALT_LENGTH = 16

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    def encrypt(self, data: bytes, passphrase: str) -> bytes:
        salt = os.urandom(self.SALT_LENGTH)
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        token = f.encrypt(data)
        return base64.b64encode(salt + token)

    def decrypt(self, data: bytes, passphrase: str) -> bytes:
        raw = base64.b64decode(data)
        salt = raw[:self.SALT_LENGTH]
        token = raw[self.SALT_LENGTH:]
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        return f.decrypt(token)


class GpgEncryptor:
    """GPG-based encryption (alternative to Fernet)."""

    @staticmethod
    def _gpg_binary() -> str | None:
        """Return the name of an available GPG binary, or None."""
        for candidate in ("gpg", "gpg2"):
            if shutil.which(candidate):
                return candidate
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._gpg_binary() is not None

    @classmethod
    def encrypt(cls, data: bytes, recipient: str | None = None) -> bytes:
        binary = cls._gpg_binary()
        if binary is None:
            raise RuntimeError("No GPG binary found (tried gpg, gpg2)")
        cmd = [binary, "--encrypt", "--armor"]
        if recipient:
            cmd.extend(["--recipient", recipient])
        else:
            cmd.append("--default-recipient-self")
        result = subprocess.run(cmd, input=data, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"GPG encrypt failed: {result.stderr.decode()}")
        return result.stdout

    @classmethod
    def decrypt(cls, data: bytes) -> bytes:
        binary = cls._gpg_binary()
        if binary is None:
            raise RuntimeError("No GPG binary found (tried gpg, gpg2)")
        result = subprocess.run(
            [binary, "--decrypt"], input=data, capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG decrypt failed: {result.stderr.decode()}")
        return result.stdout
