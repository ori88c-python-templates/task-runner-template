"""Typed container for everything the application builds once and keeps for one run."""

from dataclasses import dataclass

from app.clients import GithubClient
from app.logger import LogManager
from app.services import CsvReportWriter, GithubAdapter


@dataclass(frozen=True, slots=True)
class AppClients:
    """Clients for external resources such as databases, queues, and SDKs.

    Declare fields in topological order: a client must appear after everything
    it depends on, because that same order drives startup, and its reverse
    drives shutdown.

    Every client's ``stop()`` must be safe to call when ``start()`` never ran or
    failed partway: a failed startup still tears down every client, so the ones
    that did start are released.
    """

    github: GithubClient


@dataclass(frozen=True, slots=True)
class AppServices:
    """Business services, each constructed with the clients and child logger it needs.

    A service never reaches for a client; the composition root hands it the ones
    it declared. This is everything the ``TaskRunner`` receives.
    """

    github_adapter: GithubAdapter
    csv_report_writer: CsvReportWriter


@dataclass(frozen=True, slots=True)
class AppState:
    """Everything created at startup and shared for the lifetime of one run.

    Built and owned by the composition root; only ``services`` is handed to the
    ``TaskRunner``. Frozen and slotted on purpose: freezing stops anything from swapping a
    dependency mid-run, and slots turn a typo'd attribute into an ``AttributeError`` at the
    assignment rather than a silently ignored write.

    Attributes:
        clients: Connections to external resources.
        services: Business logic, built on top of ``clients``.
        log_manager: Source of every child logger. A direct field rather than a client,
            because it owns no connection and is needed before any client is built.
    """

    clients: AppClients
    services: AppServices
    log_manager: LogManager
