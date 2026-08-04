"""Shared kernel for the AI trading platform.

Domain models, events, configuration, security primitives, and infrastructure
ports used by every service. Services must not import each other directly —
communicate via events and this shared contract.
"""

from ai_trading_shared.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
__version__ = "0.1.0"
