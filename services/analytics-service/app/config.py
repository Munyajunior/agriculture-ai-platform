# services/analytics-service/app/config.py
"""Compatibility re-export for analytics settings."""

from .core.config import Settings, settings

__all__ = ["Settings", "settings"]
