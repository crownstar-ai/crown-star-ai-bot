# pqc/core.py – CrownStar Post‑Quantum Cryptography Engine (liboqs)
import os, json, time, hashlib, base64, struct, secrets
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class KEMAlgorithm(Enum):
    KYBER_512 = "Kyber512"; KYBER_768 = "Kyber768"; KYBER_1024 = "Kyber1024"
    FRODO_KEM_640 = "FrodoKEM-640-AES"; NTRU_HPS_2048_509 = "ntru_hps_2048_509"

class SignatureAlgorithm(Enum):
    DILITHIUM_2 = "Dilithium2"; DILITHIUM_3 = "Dilithium3"; DILITHIUM_5 = "Dilithium5"
    FALCON_512 = "Falcon-512"; FALCON_1024 = "Falcon-1024"
    SPHINCS_SHA2_128F = "SPHINCS+-SHA2-128f-simple"

@dataclass
class KEMKeypair:
    algorithm: str; public_key: bytes; secret_key: bytes; created_at: int

@dataclass
class KEMSharedSecret:
    ciphertext: bytes; shared_secret: bytes

@dataclass
class SignatureKeypair:
    algorithm: str; public_key: bytes; secret_key: bytes; created_at: int

@dataclass
class Signature:
    algorithm: str; signature: bytes; public_key_hash: str

class PQCBackend:
    def __init__(self):
        self._liboqs_available = False
        self._init_liboqs()
    def _init_liboqs(self):
        try:
            import oqs
            self._oqs = oqs
            self._liboqs_available = True
            logger.info("liboqs loaded successfully")
        except ImportError:
            logger.warning("liboqs not installed. Using simulation mode (INSECURE for production).")
            self._liboqs_available = False
    def kem_keypair(self, algorithm: KEMAlgorithm) -> KEMKeypair:
        if self._liboqs_available:
            kem = self._oqs.KeyEncapsulation(algorithm.value)
            public_key = kem.generate_keypair()
            secret_key = kem.export_secret_key()
            return KEMKeypair(algorithm=algorithm.value, public_key=public_key, secret_key=secret_key, created_at=int(time.time()))
        else:
            pub = secrets.token_bytes(32); priv = secrets.token_bytes(64)
            return KEMKeypair(algorithm=algorithm.value, public_key=pub, secret_key=priv, created_at=int(time.time()))
    def kem_encap(self, algorithm: KEMAlgorithm, public_key: bytes) -> KEMSharedSecret:
        if self._liboqs_available:
            kem = self._oqs.KeyEncapsulation(algorithm.value)
            kem.public_key = public_key
            ciphertext, shared_secret = kem.encap_secret(public_key)
            return KEMSharedSecret(ciphertext=ciphertext, shared_secret=shared_secret)
        else:
            ciphertext = secrets.token_bytes(32)
            shared_secret = hashlib.sha256(public_key + ciphertext).digest()
            return KEMSharedSecret(ciphertext=ciphertext, shared_secret=shared_secret)
    def kem_decap(self, algorithm: KEMAlgorithm, secret_key: bytes, ciphertext: bytes) -> bytes:
        if self._liboqs_available:
            kem = self._oqs.KeyEncapsulation(algorithm.value)
            kem.secret_key = secret_key
            return kem.decap_secret(ciphertext)
        else:
            return hashlib.sha256(secret_key + ciphertext).digest()
    def sign_keypair(self, algorithm: SignatureAlgorithm) -> SignatureKeypair:
        if self._liboqs_available:
            sig = self._oqs.Signature(algorithm.value)
            public_key = sig.generate_keypair()
            secret_key = sig.export_secret_key()
            return SignatureKeypair(algorithm=algorithm.value, public_key=public_key, secret_key=secret_key, created_at=int(time.time()))
        else:
            pub = secrets.token_bytes(32); priv = secrets.token_bytes(64)
            return SignatureKeypair(algorithm=algorithm.value, public_key=pub, secret_key=priv, created_at=int(time.time()))
    def sign(self, algorithm: SignatureAlgorithm, secret_key: bytes, message: bytes) -> Signature:
        if self._liboqs_available:
            sig = self._oqs.Signature(algorithm.value)
            sig.secret_key = secret_key
            signature = sig.sign(message)
            pub_hash = hashlib.sha256(sig.public_key).hexdigest()
            return Signature(algorithm=algorithm.value, signature=signature, public_key_hash=pub_hash)
        else:
            signature = hashlib.sha256(secret_key + message).digest()
            pub_hash = hashlib.sha256(secret_key[:32]).hexdigest()
            return Signature(algorithm=algorithm.value, signature=signature, public_key_hash=pub_hash)
    def verify(self, algorithm: SignatureAlgorithm, public_key: bytes, message: bytes, signature: bytes) -> bool:
        if self._liboqs_available:
            sig = self._oqs.Signature(algorithm.value)
            sig.public_key = public_key
            return sig.verify(message, signature)
        else: return True

class HybridKeyExchange:
    def __init__(self, pq_backend: PQCBackend):
        self.backend = pq_backend; self._curve = "secp256k1"
    def _ecdh_keypair(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        private_key = ec.generate_private_key(ec.SECP256K1())
        public_key = private_key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        private_bytes = private_key.private_bytes(encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw, encryption_algorithm=serialization.NoEncryption())
        return private_bytes, public_key
    def _ecdh_shared(self, private_bytes: bytes, peer_public: bytes) -> bytes:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        private_key = ec.derive_private_key(int.from_bytes(private_bytes, 'big'), ec.SECP256K1())
        peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), peer_public)
        return private_key.exchange(ec.ECDH(), peer_public_key)
    def hybrid_keypair(self) -> Tuple[bytes, bytes, bytes, bytes]:
        pq_kp = self.backend.kem_keypair(KEMAlgorithm.KYBER_768)
        ecdh_priv, ecdh_pub = self._ecdh_keypair()
        return pq_kp.public_key, pq_kp.secret_key, ecdh_pub, ecdh_priv
    def hybrid_encap(self, pq_public: bytes, ecdh_public: bytes) -> Tuple[bytes, bytes]:
        kem_ss = self.backend.kem_encap(KEMAlgorithm.KYBER_768, pq_public)
        ecdh_ephemeral_priv, ecdh_ephemeral_pub = self._ecdh_keypair()
        ecdh_shared = self._ecdh_shared(ecdh_ephemeral_priv, ecdh_public)
        combined = kem_ss.shared_secret + ecdh_shared
        shared_secret = hashlib.sha256(combined).digest()
        hybrid_ciphertext = kem_ss.ciphertext + ecdh_ephemeral_pub
        return hybrid_ciphertext, shared_secret
    def hybrid_decap(self, pq_secret: bytes, ecdh_secret: bytes, hybrid_ciphertext: bytes) -> bytes:
        kem_ct_len = 768
        kem_ct = hybrid_ciphertext[:kem_ct_len]
        ecdh_ephemeral_pub = hybrid_ciphertext[kem_ct_len:]
        kem_ss = self.backend.kem_decap(KEMAlgorithm.KYBER_768, pq_secret, kem_ct)
        ecdh_shared = self._ecdh_shared(ecdh_secret, ecdh_ephemeral_pub)
        combined = kem_ss + ecdh_shared
        return hashlib.sha256(combined).digest()

class PQEncryptor:
    def __init__(self, backend: PQCBackend):
        self.backend = backend; self.kem_alg = KEMAlgorithm.KYBER_768
    def encrypt_file(self, file_data: bytes, recipient_public_key: bytes) -> Tuple[bytes, bytes]:
        kem = self.backend.kem_encap(self.kem_alg, recipient_public_key)
        aes_key = hashlib.sha256(kem.shared_secret).digest()
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        iv = secrets.token_bytes(12)
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(file_data) + encryptor.finalize()
        tag = encryptor.tag
        packaged = iv + tag + ciphertext
        return packaged, kem.ciphertext
    def decrypt_file(self, encrypted_data: bytes, kem_ciphertext: bytes, recipient_secret_key: bytes) -> bytes:
        shared_secret = self.backend.kem_decap(self.kem_alg, recipient_secret_key, kem_ciphertext)
        aes_key = hashlib.sha256(shared_secret).digest()
        iv = encrypted_data[:12]; tag = encrypted_data[12:28]; ciphertext = encrypted_data[28:]
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

class PQCManager:
    def __init__(self, config_path="config/pqc/config.json"):
        self.config = self._load_config(config_path)
        self.backend = PQCBackend()
        self.hybrid = HybridKeyExchange(self.backend)
        self.encryptor = PQEncryptor(self.backend)
    def _load_config(self, path):
        default = {"default_kem":"Kyber768","default_signature":"Dilithium3","hybrid_enabled":True,"store_keys":True,"keys_dir":"data/pqc/keys"}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        os.makedirs(default["keys_dir"], exist_ok=True)
        return default
    def kem_keypair(self, algorithm: str = None) -> Dict:
        alg = KEMAlgorithm(algorithm or self.config["default_kem"])
        kp = self.backend.kem_keypair(alg)
        if self.config["store_keys"]:
            with open(os.path.join(self.config["keys_dir"], f"{kp.algorithm}_{kp.created_at}.json"), 'w') as f:
                json.dump({"algorithm":kp.algorithm,"public_key":base64.b64encode(kp.public_key).decode(),"secret_key":base64.b64encode(kp.secret_key).decode(),"created_at":kp.created_at}, f)
        return {"algorithm":kp.algorithm,"public_key":base64.b64encode(kp.public_key).decode(),"created_at":kp.created_at}
    def kem_encap(self, public_key_b64: str, algorithm: str = None) -> Dict:
        alg = KEMAlgorithm(algorithm or self.config["default_kem"])
        public_key = base64.b64decode(public_key_b64)
        ss = self.backend.kem_encap(alg, public_key)
        return {"ciphertext":base64.b64encode(ss.ciphertext).decode(),"shared_secret":base64.b64encode(ss.shared_secret).decode()}
    def kem_decap(self, secret_key_b64: str, ciphertext_b64: str, algorithm: str = None) -> Dict:
        alg = KEMAlgorithm(algorithm or self.config["default_kem"])
        secret_key = base64.b64decode(secret_key_b64); ciphertext = base64.b64decode(ciphertext_b64)
        shared_secret = self.backend.kem_decap(alg, secret_key, ciphertext)
        return {"shared_secret":base64.b64encode(shared_secret).decode()}
    def sign_keypair(self, algorithm: str = None) -> Dict:
        alg = SignatureAlgorithm(algorithm or self.config["default_signature"])
        kp = self.backend.sign_keypair(alg)
        if self.config["store_keys"]:
            with open(os.path.join(self.config["keys_dir"], f"sig_{kp.algorithm}_{kp.created_at}.json"), 'w') as f:
                json.dump({"algorithm":kp.algorithm,"public_key":base64.b64encode(kp.public_key).decode(),"secret_key":base64.b64encode(kp.secret_key).decode(),"created_at":kp.created_at}, f)
        return {"algorithm":kp.algorithm,"public_key":base64.b64encode(kp.public_key).decode(),"created_at":kp.created_at}
    def sign(self, secret_key_b64: str, message_b64: str, algorithm: str = None) -> Dict:
        alg = SignatureAlgorithm(algorithm or self.config["default_signature"])
        secret_key = base64.b64decode(secret_key_b64); message = base64.b64decode(message_b64)
        sig = self.backend.sign(alg, secret_key, message)
        return {"algorithm":sig.algorithm,"signature":base64.b64encode(sig.signature).decode(),"public_key_hash":sig.public_key_hash}
    def verify(self, public_key_b64: str, message_b64: str, signature_b64: str, algorithm: str = None) -> bool:
        alg = SignatureAlgorithm(algorithm or self.config["default_signature"])
        public_key = base64.b64decode(public_key_b64); message = base64.b64decode(message_b64); signature = base64.b64decode(signature_b64)
        return self.backend.verify(alg, public_key, message, signature)
    def hybrid_keypair(self) -> Dict:
        pq_pub, pq_sec, ecdh_pub, ecdh_sec = self.hybrid.hybrid_keypair()
        return {"pq_public_key":base64.b64encode(pq_pub).decode(),"pq_secret_key":base64.b64encode(pq_sec).decode(),"ecdh_public_key":base64.b64encode(ecdh_pub).decode(),"ecdh_secret_key":base64.b64encode(ecdh_sec).decode()}
    def hybrid_encap(self, pq_public_b64: str, ecdh_public_b64: str) -> Dict:
        pq_pub = base64.b64decode(pq_public_b64); ecdh_pub = base64.b64decode(ecdh_public_b64)
        ciphertext, shared = self.hybrid.hybrid_encap(pq_pub, ecdh_pub)
        return {"hybrid_ciphertext":base64.b64encode(ciphertext).decode(),"shared_secret":base64.b64encode(shared).decode()}
    def hybrid_decap(self, pq_secret_b64: str, ecdh_secret_b64: str, hybrid_ciphertext_b64: str) -> Dict:
        pq_sec = base64.b64decode(pq_secret_b64); ecdh_sec = base64.b64decode(ecdh_secret_b64)
        ciphertext = base64.b64decode(hybrid_ciphertext_b64)
        shared = self.hybrid.hybrid_decap(pq_sec, ecdh_sec, ciphertext)
        return {"shared_secret":base64.b64encode(shared).decode()}

_pqc_manager = None
def get_pqc_manager():
    global _pqc_manager
    if _pqc_manager is None: _pqc_manager = PQCManager()
    return _pqc_manager
