"""Exceptions raised by uniprotptmpy."""

from __future__ import annotations


class UniprotPtmError(Exception):
    """Base class for uniprotptmpy errors (e.g. a duplicate accession in a PtmDatabase)."""


class UniprotPtmParseError(UniprotPtmError, ValueError):
    """Malformed ptmlist.txt input or correction formula. Also a ValueError."""
