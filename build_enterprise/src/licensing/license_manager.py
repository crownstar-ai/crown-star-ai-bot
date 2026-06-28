# ====================================================================================================
# license_manager.py – License Key Validation for CrownStar‑Absolute
# Supports:
#   - JSON license file with signature
#   - Offline validation (no network required)
#   - Expiry dates and grace periods
#   - Hardware binding (optional)
#   - Feature entitlements (override tier defaults)
# ====================================================================================================

import json
import hashlib
import hmac
import base64
import time
import uuid
import platform
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger("CrownStar.License")

# --------------------------------------------------------------------
# License Data Structure
# --------------------------------------------------------------------
@dataclass
class LicenseInfo:
    """Parsed license information."""
    license_key: str
    tier: str
    activated: bool
    activation_time: Optional[float]
    expiry_time: Optional[float]          # None = never expires
    grace_period_days: int = 7
    features_override: List[str] = None   # additional features beyond tier
    machine_id: Optional[str] = None      # hardware fingerprint
    signature: Optional[str] = None
    issued_to: str = ""
    issued_by: str = "CrownStar-Absolute"
    metadata: Dict = None
    
    def is_expired(self) -> bool:
        """Check if license has expired (including grace period)."""
        if self.expiry_time is None:
            return False
        now = time.time()
        if now <= self.expiry_time:
            return False
        # Within grace period?
        grace_sec = self.grace_period_days * 86400
        if now <= self.expiry_time + grace_sec:
            logger.warning(f"License expired but within {self.grace_period_days}‑day grace period")
            return False
        return True
    
    def days_remaining(self) -> Optional[int]:
        """Return days until expiry, or None if never expires."""
        if self.expiry_time is None:
            return None
        remaining = self.expiry_time - time.time()
        if remaining < 0:
            remaining = 0 - (self.expiry_time + (self.grace_period_days * 86400) - time.time())
        return max(0, int(remaining // 86400))
    
    def to_dict(self) -> Dict:
        return {
            "license_key": self.license_key,
            "tier": self.tier,
            "activated": self.activated,
            "activation_time": self.activation_time,
            "expiry_time": self.expiry_time,
            "grace_period_days": self.grace_period_days,
            "features_override": self.features_override,
            "machine_id": self.machine_id,
            "signature": self.signature,
            "issued_to": self.issued_to,
            "issued_by": self.issued_by,
            "metadata": self.metadata or {}
        }

# --------------------------------------------------------------------
# License Manager Core
# --------------------------------------------------------------------
class LicenseManager:
    """
    Manages license key validation, storage, and offline verification.
    """
    
    # Secret key for HMAC (in production, use a securely stored key)
    _SECRET_KEY = b"crownstar_absolute_secret_key_2026_change_in_production"
    
    def __init__(self, license_file: str = "data/license.json", 
                 require_machine_binding: bool = False):
        self.license_file = Path(license_file)
        self.require_machine_binding = require_machine_binding
        self._license: Optional[LicenseInfo] = None
        self._machine_id = self._get_machine_id()
        self._load()
    
    def _get_machine_id(self) -> str:
        """Generate a unique machine identifier (hardware fingerprint)."""
        # Combine multiple system identifiers
        identifiers = [
            platform.node(),           # hostname
            platform.machine(),        # architecture
            platform.processor(),
            str(uuid.getnode())        # MAC address (may be virtual)
        ]
        combined = "|".join(identifiers)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _generate_signature(self, data: Dict) -> str:
        """Generate HMAC signature for license data."""
        # Remove signature field before hashing
        data_copy = {k: v for k, v in data.items() if k != "signature"}
        json_str = json.dumps(data_copy, sort_keys=True)
        signature = hmac.new(self._SECRET_KEY, json_str.encode(), hashlib.sha256).digest()
        return base64.b64encode(signature).decode()
    
    def _verify_signature(self, data: Dict) -> bool:
        """Verify HMAC signature of license data."""
        if "signature" not in data:
            return False
        stored_sig = data["signature"]
        computed_sig = self._generate_signature(data)
        return hmac.compare_digest(stored_sig.encode(), computed_sig.encode())
    
    def _load(self):
        """Load license from disk and validate signature."""
        if not self.license_file.exists():
            self._license = None
            return
        try:
            with open(self.license_file, 'r') as f:
                data = json.load(f)
            if not self._verify_signature(data):
                logger.error("License signature verification failed")
                self._license = None
                return
            self._license = LicenseInfo(
                license_key=data.get("license_key", ""),
                tier=data.get("tier", "free"),
                activated=data.get("activated", False),
                activation_time=data.get("activation_time"),
                expiry_time=data.get("expiry_time"),
                grace_period_days=data.get("grace_period_days", 7),
                features_override=data.get("features_override", []),
                machine_id=data.get("machine_id"),
                signature=data.get("signature"),
                issued_to=data.get("issued_to", ""),
                issued_by=data.get("issued_by", "CrownStar-Absolute"),
                metadata=data.get("metadata", {})
            )
            # Verify machine binding if required
            if self.require_machine_binding:
                if self._license.machine_id != self._machine_id:
                    logger.error("Machine binding mismatch – license invalid on this device")
                    self._license = None
            logger.info(f"License loaded: tier={self._license.tier}, activated={self._license.activated}")
        except Exception as e:
            logger.error(f"Failed to load license: {e}")
            self._license = None
    
    def _save(self):
        """Save license to disk with signature."""
        if self._license is None:
            if self.license_file.exists():
                self.license_file.unlink()
            return
        data = self._license.to_dict()
        data["signature"] = self._generate_signature(data)
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.license_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug("License saved")
    
    # --------------------------------------------------------------------
    # Activation / Validation
    # --------------------------------------------------------------------
    def activate(self, license_key: str, offline_key: Optional[str] = None,
                 issued_to: str = "", expiry_days: Optional[int] = None) -> Tuple[bool, str]:
        """
        Activate a license key.
        In production, this would call a validation server.
        For offline activation, use offline_key (pre‑computed challenge).
        """
        # Simple format validation
        if not license_key.startswith("CROWNSTAR-"):
            return False, "Invalid license key format. Must start with 'CROWNSTAR-'"
        
        parts = license_key.split('-')
        if len(parts) != 4:
            return False, "Invalid license key format. Expected CROWNSTAR-XXXX-XXXX-TIER"
        
        # Determine tier from key suffix
        suffix = parts[-1].upper()
        tier_map = {
            "FREE": "free",
            "BASIC": "basic",
            "PRO": "pro",
            "ENT": "enterprise"
        }
        tier = tier_map.get(suffix, "free")
        
        # In production, validate against a server or offline challenge
        if offline_key:
            # Validate offline challenge (simplified)
            expected = hashlib.sha256(f"{license_key}{self._machine_id}".encode()).hexdigest()[:16]
            if offline_key != expected:
                return False, "Offline activation code invalid"
        else:
            # For demo, accept all valid formats (but warn)
            logger.warning("Using demo activation – not secure for production")
        
        # Set expiry
        expiry_time = None
        if expiry_days:
            expiry_time = time.time() + expiry_days * 86400
        
        self._license = LicenseInfo(
            license_key=license_key,
            tier=tier,
            activated=True,
            activation_time=time.time(),
            expiry_time=expiry_time,
            grace_period_days=7,
            features_override=[],
            machine_id=self._machine_id if self.require_machine_binding else None,
            issued_to=issued_to,
            metadata={"activation_method": "offline" if offline_key else "demo"}
        )
        self._save()
        logger.info(f"License activated for tier: {tier}")
        return True, f"License activated successfully for {tier} tier"
    
    def deactivate(self) -> bool:
        """Deactivate the current license (remove local license file)."""
        if self.license_file.exists():
            self.license_file.unlink()
        self._license = None
        logger.info("License deactivated")
        return True
    
    def is_licensed(self) -> bool:
        """Check if a valid license is present and not expired."""
        if self._license is None:
            return False
        if not self._license.activated:
            return False
        if self._license.is_expired():
            logger.warning("License has expired")
            return False
        return True
    
    def get_current_tier(self) -> str:
        """Return the tier of the current license (or 'free' if no license)."""
        if self.is_licensed():
            return self._license.tier
        return "free"
    
    def get_license_info(self) -> Optional[Dict]:
        """Return license information (safe for display)."""
        if self._license is None:
            return {"activated": False}
        return {
            "activated": True,
            "tier": self._license.tier,
            "activation_time": self._license.activation_time,
            "expiry_time": self._license.expiry_time,
            "days_remaining": self._license.days_remaining(),
            "issued_to": self._license.issued_to,
            "has_expiry": self._license.expiry_time is not None,
            "is_expired": self._license.is_expired()
        }
    
    def get_features(self) -> List[str]:
        """Return the feature list for the current license (tier defaults + overrides)."""
        if not self.is_licensed():
            from .tiers import get_tier_config
            return get_tier_config("free").features
        from .tiers import get_tier_config
        base_features = get_tier_config(self._license.tier).features
        if self._license.features_override:
            return list(set(base_features + self._license.features_override))
        return base_features
    
    def has_feature(self, feature: str) -> bool:
        """Check if the current license includes a specific feature."""
        return feature in self.get_features()
    
    # --------------------------------------------------------------------
    # License maintenance
    # --------------------------------------------------------------------
    def refresh(self):
        """Re‑load license from disk (e.g., after external update)."""
        self._load()
    
    def get_status_message(self) -> str:
        """Return a human‑readable status message."""
        if not self.is_licensed():
            return "⚠️ No valid license found. Using free tier with limited features."
        info = self.get_license_info()
        if info.get("is_expired"):
            return f"⚠️ License expired. Please renew. Grace period may apply."
        days = info.get("days_remaining")
        if days is not None and days < 7:
            return f"⚠️ License expires in {days} days. Please renew soon."
        tier = info.get("tier", "free")
        return f"✓ Valid license ({tier} tier) – all features enabled."

# --------------------------------------------------------------------
# Integration with ControlShell (add license checking to tier enforcement)
# --------------------------------------------------------------------
def integrate_license_with_shell(shell):
    """Augment ControlShell with license manager features."""
    from .license_manager import LicenseManager
    if not hasattr(shell, '_license_manager'):
        shell._license_manager = LicenseManager()
        logger.info("License manager integrated into ControlShell")
    
    # Override can_make_request to also check license validity
    original_can = shell.can_make_request if hasattr(shell, 'can_make_request') else None
    
    def can_make_request_with_license(tier: str, user_id: str = "default") -> bool:
        if not shell._license_manager.is_licensed():
            # Allow free tier if no license, but with a warning
            if tier == "free":
                return True
            return False
        return original_can(tier, user_id) if original_can else True
    shell.can_make_request = can_make_request_with_license
    
    # Add convenience methods
    def get_license_status(self) -> Dict:
        return self._license_manager.get_license_info()
    shell.get_license_status = get_license_status.__get__(shell, ControlShell)
    
    def get_license_features(self) -> List[str]:
        return self._license_manager.get_features()
    shell.get_license_features = get_license_features.__get__(shell, ControlShell)
    
    def has_feature_licensed(self, feature: str) -> bool:
        return self._license_manager.has_feature(feature)
    shell.has_feature_licensed = has_feature_licensed.__get__(shell, ControlShell)

# --------------------------------------------------------------------
# Standalone license check (for CLI)
# --------------------------------------------------------------------
def check_license_status() -> str:
    """Print license status to console (useful for diagnostics)."""
    mgr = LicenseManager()
    return mgr.get_status_message()

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
# Create license manager
license_mgr = LicenseManager()

# Activate with a demo key
if not license_mgr.is_licensed():
    success, msg = license_mgr.activate("CROWNSTAR-DEMO-ABCD-PRO", issued_to="Test User")
    print(msg)

# Check status
print(license_mgr.get_status_message())
print("Features:", license_mgr.get_features())

# Check specific feature
if license_mgr.has_feature("cortex_full"):
    print("Full Internet Cortex available")

# Deactivate
# license_mgr.deactivate()
"""

# ====================================================================================================
# END OF license_manager.py (31,492 characters)
# ====================================================================================================
