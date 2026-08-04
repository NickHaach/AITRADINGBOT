from __future__ import annotations
"""Simple dependency injection container."""

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Container:
    """Minimal service locator / DI container for FastAPI and workers."""

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[[], Any]] = {}

    def register_singleton(self, iface: type[T], instance: T) -> None:
        self._singletons[iface] = instance

    def register_factory(self, iface: type[T], factory: Callable[[], T]) -> None:
        self._factories[iface] = factory

    def resolve(self, iface: type[T]) -> T:
        if iface in self._singletons:
            return self._singletons[iface]  # type: ignore[no-any-return]
        if iface in self._factories:
            instance = self._factories[iface]()
            self._singletons[iface] = instance
            return instance  # type: ignore[no-any-return]
        raise KeyError(f"No registration for {iface}")

    def clear(self) -> None:
        self._singletons.clear()
        self._factories.clear()
