"""Immutable identity constants that must not be overridden by the environment.

The log ``app`` identity is a contract with observability: dashboards and alerts filter
on it. It is not a deployment setting: putting it in ``.env`` would invite a typo to
silently detach every log line from its Grafana filter.
"""

from typing import Final

APP_NAME: Final = "task-runner-template"
