# security/encryption.py – Encryption service for sensitive data
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import json
from pathlib import Path

class EncryptionService:
    def __init__(self, key_file: str = "config/encryption.key"):
        self.key_file = Path(key_file)
        self._master_key = None
        self._fernet = None
        self._load_or_create_key()
    
    def _load_or_create_key(self):
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self._master_key = f.read()
        else:
            self._master_key = Fernet.generate_key()
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(self._master_key)
        self._fernet = Fernet(self._master_key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data using Fernet (simpler)"""
        return self._fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self._fernet.decrypt(encrypted.encode()).decode()
    
    def encrypt_aes(self, data: bytes, associated_data: bytes = None) -> bytes:
        """AES-256-GCM encryption for larger data"""
        aesgcm = AESGCM(self._master_key[:32])
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, associated_data)
        return nonce + ct
    
    def decrypt_aes(self, ciphertext: bytes, associated_data: bytes = None) -> bytes:
        nonce = ciphertext[:12]
        ct = ciphertext[12:]
        aesgcm = AESGCM(self._master_key[:32])
        return aesgcm.decrypt(nonce, ct, associated_data)
    
    def hash_password(self, password: str, salt: bytes = None) -> tuple:
        """Argon2-style password hashing (fallback to PBKDF2)"""
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode(), base64.b64encode(salt).decode()
    
    def verify_password(self, password: str, stored_hash: str, stored_salt: str) -> bool:
        salt = base64.b64decode(stored_salt)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        computed = base64.urlsafe_b64encode(kdf.derive(password.encode())).decode()
        return computed == stored_hash

# Singleton instance
_encryption = None
def get_encryption():
    global _encryption
    if _encryption is None:
        _encryption = EncryptionService()
    return _encryption
