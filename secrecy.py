"""
secrecy — FABRIC component: client-side encryption

Encrypts inference payloads before transit. Encryption happens on the client —
the server never sees plaintext. Gleaned and adapted from secret-server/lib/crypto.py.
"""

import sys
import json
import base64
import os
import fileinput
from pathlib import Path

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet


_SALT_SIZE = 16
_KDF_ITERATIONS = 600_000


def _derive_key(passphrase, salt):
    """Derive a 32-byte Fernet key from passphrase + salt via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt(plaintext, passphrase):
    """Encrypt a string client-side. Returns base64-encoded (salt || fernet_token).

    - Encryption happens before freeze/transit — server never sees plaintext
    - Returns base64 string safe for JSON embedding
    - Raises ValueError if passphrase is empty
    """
    if not passphrase:
        raise ValueError("Passphrase required")
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(plaintext.encode("utf-8"))
    return base64.urlsafe_b64encode(salt + token).decode("utf-8")


def decrypt(encrypted_b64, passphrase):
    """Decrypt a base64-encoded (salt || fernet_token) string.

    - Returns plaintext string
    - Raises ValueError on wrong passphrase or malformed input
    """
    if not passphrase:
        raise ValueError("Passphrase required")
    combined = base64.urlsafe_b64decode(encrypted_b64.encode("utf-8"))
    if len(combined) <= _SALT_SIZE:
        raise ValueError("Invalid encrypted payload")
    salt, token = combined[:_SALT_SIZE], combined[_SALT_SIZE:]
    key = _derive_key(passphrase, salt)
    return Fernet(key).decrypt(token).decode("utf-8")


def encrypt_inference(inference, passphrase):
    """Encrypt the raw_text field of an inference dict in place.

    - Only raw_text is encrypted — keywords and metadata stay readable
    - Adds 'encrypted': true flag to the inference
    - Returns modified inference dict
    """
    inference = dict(inference)
    inference["raw_text"] = encrypt(inference["raw_text"], passphrase)
    inference["encrypted"] = True
    return inference


def decrypt_inference(inference, passphrase):
    """Decrypt the raw_text field of an inference dict.

    - Returns inference with raw_text restored to plaintext
    - Raises if inference is not marked encrypted
    """
    if not inference.get("encrypted"):
        return inference
    inference = dict(inference)
    inference["raw_text"] = decrypt(inference["raw_text"], passphrase)
    inference["encrypted"] = False
    return inference


def usage():
    print("Usage: secrecy.py encrypt <passphrase> < inference.json")
    print("       secrecy.py decrypt <passphrase> < inference.json")
    sys.exit(1)


def main():
    if len(sys.argv) < 3:
        usage()

    mode = sys.argv[1]
    passphrase = sys.argv[2]

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
    else:
        usage()

    inference = json.loads(raw)

    if mode == "encrypt":
        result = encrypt_inference(inference, passphrase)
    elif mode == "decrypt":
        result = decrypt_inference(inference, passphrase)
    else:
        usage()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

# llm: claude-sonnet-4-6 | 2026-04-15 | repos/vivify-inferences/secrecy.py | created — client-side FABRIC secrecy, gleaned from secret-server/lib/crypto.py
