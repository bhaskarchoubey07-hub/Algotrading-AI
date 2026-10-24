"""DhanHQ Authentication and Secrets Governance.

Manages API credentials, token inspection, expiration heuristics, and redaction.
Strictly forbids logging raw credentials or exposing tokens to client/logs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from app.brokers.dhan.exceptions import DhanAuthenticationError
from app.brokers.dhan.normalizers import redact_sensitive_data
from app.config import settings

logger = logging.getLogger("algotrade.dhan.auth")


@dataclass
class DhanCredentialStatus:
    client_id_configured: bool
    access_token_configured: bool
    client_id_masked: str
    access_token_masked: str
    environment: str
    is_valid: bool
    live_gate_closed: bool = True
    token_character_length: int = 0
    instructions: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id_configured": self.client_id_configured,
            "access_token_configured": self.access_token_configured,
            "client_id_masked": self.client_id_masked,
            "access_token_masked": self.access_token_masked,
            "environment": self.environment,
            "is_valid": self.is_valid,
            "live_gate_closed": self.live_gate_closed,
            "token_character_length": self.token_character_length,
            "instructions": self.instructions,
        }


class DhanAuthManager:
    """Validates and governs DhanHQ v2 credentials with zero credential exposure."""

    def __init__(self, client_id: str | None = None, access_token: str | None = None, env: str | None = None) -> None:
        self._client_id = (client_id or settings.dhan_client_id or "").strip()
        self._access_token = (access_token or settings.dhan_access_token or "").strip()
        self._env = (env or settings.dhan_env or "sandbox").strip().lower()

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def environment(self) -> str:
        return self._env

    def is_configured(self) -> bool:
        """Checks if both Client ID and Access Token are present."""
        return bool(self._client_id and self._access_token)

    def mask_string(self, val: str, visible_start: int = 3, visible_end: int = 3) -> str:
        """Masks sensitive strings (e.g. '100****001' or 'eyJh****9X1')."""
        if not val:
            return "NOT_CONFIGURED"
        if len(val) <= visible_start + visible_end:
            return "*" * len(val)
        return f"{val[:visible_start]}{'*' * (len(val) - visible_start - visible_end)}{val[-visible_end:]}"

    def get_credential_status(self) -> DhanCredentialStatus:
        """Returns safe, redacted status of credentials for UI and diagnostics."""
        is_valid = self.is_configured() and len(self._access_token) >= 20
        instructions = (
            "DhanHQ Token Setup: Generate your Access Token from Dhan Web Portal -> "
            "My Profile -> DhanHQ Trading APIs -> Access Token. Configure in .env as "
            "DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN."
        )
        return DhanCredentialStatus(
            client_id_configured=bool(self._client_id),
            access_token_configured=bool(self._access_token),
            client_id_masked=self.mask_string(self._client_id, 2, 2),
            access_token_masked=self.mask_string(self._access_token, 4, 4),
            environment=self._env,
            is_valid=is_valid,
            live_gate_closed=True,
            token_character_length=len(self._access_token),
            instructions=instructions,
        )

    def validate_or_raise(self) -> None:
        """Validates credentials; raises DhanAuthenticationError if missing or malformed."""
        if not self._client_id:
            raise DhanAuthenticationError(
                "Dhan Client ID is missing. Set DHAN_CLIENT_ID in .env or via settings.",
                error_code="MISSING_CLIENT_ID",
            )
        if not self._access_token:
            raise DhanAuthenticationError(
                "Dhan Access Token is missing. Set DHAN_ACCESS_TOKEN in .env or via settings.",
                error_code="MISSING_ACCESS_TOKEN",
            )
        if len(self._access_token) < 20:
            raise DhanAuthenticationError(
                "Dhan Access Token appears truncated or invalid (too short).",
                error_code="INVALID_ACCESS_TOKEN",
            )
