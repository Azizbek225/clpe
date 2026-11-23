"""Provayderlar reestri. Plugin modullar `register_provider` orqali yangi adapter qo'sha oladi."""
from __future__ import annotations

from collections.abc import Callable

from app.labengine.providers.base import VirtualizationProvider

_FACTORIES: dict[str, Callable[[], VirtualizationProvider]] = {}
_INSTANCES: dict[str, VirtualizationProvider] = {}


def register_provider(name: str, factory: Callable[[], VirtualizationProvider]) -> None:
    _FACTORIES[name] = factory


def get_provider(name: str) -> VirtualizationProvider:
    if name not in _INSTANCES:
        if name not in _FACTORIES:
            raise KeyError(f"Noma'lum virtualizatsiya provayderi: {name}")
        _INSTANCES[name] = _FACTORIES[name]()
    return _INSTANCES[name]


def available_providers() -> list[str]:
    return sorted(_FACTORIES)


def _mock() -> VirtualizationProvider:
    from app.labengine.providers.mock import MockProvider
    return MockProvider()


def _docker() -> VirtualizationProvider:
    from app.labengine.providers.docker_provider import DockerProvider
    return DockerProvider()


def _vbox() -> VirtualizationProvider:
    from app.labengine.providers.virtualbox import VirtualBoxProvider
    return VirtualBoxProvider()


def _libvirt() -> VirtualizationProvider:
    from app.labengine.providers.libvirt_provider import LibvirtProvider
    return LibvirtProvider()


register_provider("mock", _mock)
register_provider("docker", _docker)
register_provider("virtualbox", _vbox)
register_provider("libvirt", _libvirt)
