"""Append-only service registry.

The single place capability services register themselves (`services/README.md`). Registration
is **append-only**: re-registering a name raises rather than silently overwriting, so two
independently-developed services (or parallel agent sessions) cannot clobber each other — the
R7 "no bespoke/duplicate registrations" mitigation (`risks.md`). Use `@registry.register` as a
decorator at class definition so a service is registered by importing its module
(entry-point style).
"""

from __future__ import annotations

from .base import Service


class ServiceRegistry:
    """A name -> Service-class map that refuses duplicate or unnamed registrations."""

    def __init__(self) -> None:
        self._services: dict[str, type[Service]] = {}

    def register(self, service_cls: type[Service]) -> type[Service]:
        """Register a service class by its `name`. Returns the class (usable as a decorator)."""
        name = getattr(service_cls, "name", None)
        if not name:
            raise ValueError(f"{service_cls.__name__} must set a non-empty 'name' to register")
        if name in self._services:
            existing = self._services[name].__name__
            raise ValueError(
                f"service {name!r} is already registered to {existing}; "
                f"registrations are append-only (R7)"
            )
        self._services[name] = service_cls
        return service_cls

    def get(self, name: str) -> type[Service]:
        try:
            return self._services[name]
        except KeyError:
            raise KeyError(f"no service registered as {name!r}; known: {self.names()}") from None

    def __contains__(self, name: object) -> bool:
        return name in self._services

    def __len__(self) -> int:
        return len(self._services)

    def names(self) -> list[str]:
        return sorted(self._services)


# Module-level singleton every service registers into.
registry = ServiceRegistry()
