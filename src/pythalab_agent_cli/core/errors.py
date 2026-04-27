"""Typed exceptions used by the agent runtime."""


class PythalabError(Exception):
    """Base exception for pythalab-agent-cli."""


class ConfigError(PythalabError):
    """Raised when configuration cannot be loaded or validated."""


class ModelError(PythalabError):
    """Raised when model calls fail."""


class OutputParseError(PythalabError):
    """Raised when structured model output cannot be parsed."""


class PatchError(PythalabError):
    """Raised for malformed or non-applicable patches."""


class SecurityError(PythalabError):
    """Raised when a path, command, prompt, or patch violates policy."""


class ValidationError(PythalabError):
    """Raised for validation pipeline failures when fail-fast mode is enabled."""
