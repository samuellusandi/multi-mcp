"""Custom exceptions for MultiMCP."""

class MultiMCPError(Exception):
    """Base exception for MultiMCP errors."""
    pass

class ConfigurationError(MultiMCPError):
    """Raised when configuration is invalid."""
    pass

class ClientInitializationError(MultiMCPError):
    """Raised when client initialization fails."""
    pass

class TransportError(MultiMCPError):
    """Raised when transport setup fails."""
    pass
