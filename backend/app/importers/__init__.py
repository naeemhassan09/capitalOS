"""Pluggable CSV importer registry.

Importers self-describe via :attr:`importer_type`. New banks are added simply
by creating a subclass of :class:`BaseTransactionImporter` and registering it
in :data:`IMPORTER_REGISTRY` below — no orchestration code needs to change.
"""

from __future__ import annotations

from app.importers.aib import AibCsvImporter
from app.importers.base import (
    BaseTransactionImporter,
    ImporterError,
    ParsedRow,
)
from app.importers.generic import GenericCsvImporter
from app.importers.manual_template import ManualTemplateImporter
from app.importers.revolut import RevolutCsvImporter

# Order matters for auto-detection: more specific importers first, the generic
# fallback last (it never auto-detects, but keeps a stable ordering for the UI).
_IMPORTER_CLASSES: tuple[type[BaseTransactionImporter], ...] = (
    AibCsvImporter,
    RevolutCsvImporter,
    ManualTemplateImporter,
    GenericCsvImporter,
)

IMPORTER_REGISTRY: dict[str, type[BaseTransactionImporter]] = {
    cls.importer_type: cls for cls in _IMPORTER_CLASSES
}


def get_importer_class(importer_type: str) -> type[BaseTransactionImporter] | None:
    return IMPORTER_REGISTRY.get(importer_type)


def detect_importer(headers: list[str]) -> type[BaseTransactionImporter] | None:
    """Return the first importer whose ``detect`` recognises these headers."""
    for cls in _IMPORTER_CLASSES:
        if cls.detect(headers):
            return cls
    return None


__all__ = [
    "IMPORTER_REGISTRY",
    "BaseTransactionImporter",
    "ImporterError",
    "ParsedRow",
    "AibCsvImporter",
    "RevolutCsvImporter",
    "GenericCsvImporter",
    "ManualTemplateImporter",
    "get_importer_class",
    "detect_importer",
]
