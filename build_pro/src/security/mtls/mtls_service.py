# security/mtls/mtls_service.py – mTLS certificate validation
import ssl
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import logging

logger = logging.getLogger("crownstar.security.mtls")

class MTLSValidator:
    def __init__(self, ca_cert_path: str = "data/security/certs/ca.crt", require_client_cert: bool = True):
        self.ca_cert_path = Path(ca_cert_path)
        self.require_client_cert = require_client_cert
        self._ca_cert = None
        self._load_ca()
    
    def _load_ca(self):
        if self.ca_cert_path.exists():
            with open(self.ca_cert_path, "rb") as f:
                self._ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            logger.info("mTLS CA certificate loaded")
    
    def validate_certificate(self, cert_pem: bytes) -> Tuple[bool, Dict]:
        """Validate client certificate against CA and return attributes"""
        result = {"valid": False, "subject": {}, "issuer": {}, "error": None}
        try:
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            # Check against CA
            if self._ca_cert:
                pub_key = self._ca_cert.public_key()
                try:
                    cert.verify_directly_issued_by(self._ca_cert)
                except:
                    result["error"] = "Certificate not issued by trusted CA"
                    return result
            # Extract subject
            subject = cert.subject
            for attr in subject:
                result["subject"][attr.oid._name] = attr.value
            result["valid"] = True
            result["fingerprint"] = cert.fingerprint(hashes.SHA256()).hex()
            result["not_before"] = cert.not_valid_before.isoformat()
            result["not_after"] = cert.not_valid_after.isoformat()
        except Exception as e:
            result["error"] = str(e)
        return result
    
    def create_server_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for server with mTLS enabled"""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.verify_mode = ssl.CERT_REQUIRED if self.require_client_cert else ssl.CERT_OPTIONAL
        context.load_verify_locations(cafile=str(self.ca_cert_path))
        # Load server certificate and key
        cert_file = Path("data/security/certs/server.crt")
        key_file = Path("data/security/certs/server.key")
        if cert_file.exists() and key_file.exists():
            context.load_cert_chain(str(cert_file), str(key_file))
        return context

_mtls = None
def get_mtls_validator():
    global _mtls
    if _mtls is None:
        _mtls = MTLSValidator()
    return _mtls
