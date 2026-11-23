"""Validator engine (11-bo'lim). Har bir tekshiruv turi — alohida plagin funksiya.

Yangi tur qo'shish:
    from app.labengine.validators import register_validator, ValidationResult

    @register_validator("my_check")
    def my_check(ctx): ...
va modulni CLPE_PLUGIN_MODULES ga qo'shing. Manifestda `validation: {type: my_check, ...}`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.labengine.validators.base import ValidationContext, ValidationResult

_REGISTRY: dict[str, Callable[[ValidationContext], ValidationResult]] = {}


def register_validator(name: str):
    def deco(fn: Callable[[ValidationContext], ValidationResult]):
        _REGISTRY[name] = fn
        return fn
    return deco


def get_validator(name: str) -> Callable[[ValidationContext], ValidationResult]:
    if name not in _REGISTRY:
        raise KeyError(name)
    return _REGISTRY[name]


def validator_types() -> set[str]:
    return set(_REGISTRY)


from app.labengine.validators import builtin  # noqa: E402,F401  (o'rnatilgan validatorlar)

__all__ = ["register_validator", "get_validator", "validator_types", "ValidationContext", "ValidationResult",
           "dataclass", "field", "Any"]
