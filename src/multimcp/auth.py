"""Authentication utilities for MultiMCP."""

import base64
from typing import Optional

from src.utils.logger import get_logger

from .constants import AUTH_BASE64_MSG, AUTH_ENABLED_MSG, AUTH_WARNING_MSG


class AuthenticationManager:
    """Handles authentication setup and URL prefix generation."""

    def __init__(self, basic_auth: Optional[str] = None):
        """Initialize the AuthenticationManager."""
        self.basic_auth = basic_auth
        self.logger = get_logger("multi_mcp.AuthManager")
        self._base64_auth: Optional[str] = None
        self._url_prefix: str = ""
        self._setup_auth()

    def _setup_auth(self) -> None:
        """Set up authentication and calculate URL prefix."""
        if self.basic_auth:
            self.logger.info(AUTH_ENABLED_MSG.format(self.basic_auth))
            self._base64_auth = base64.b64encode(self.basic_auth.encode("UTF-8")).decode()
            self.logger.info(AUTH_BASE64_MSG.format(self._base64_auth))
            self._url_prefix = f"/{self._base64_auth}"
        else:
            self.logger.warning(AUTH_WARNING_MSG)
            self._url_prefix = ""

    @property
    def url_prefix(self) -> str:
        """Get the URL prefix for routes."""
        return self._url_prefix

    @property
    def base64_auth(self) -> Optional[str]:
        """Get the base64 encoded authentication string."""
        return self._base64_auth
