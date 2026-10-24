"""Composition root: builds the application state and owns its startup and shutdown order."""

from app.lifecycle.lifecycle_manager import LifecycleManager

__all__ = ["LifecycleManager"]
