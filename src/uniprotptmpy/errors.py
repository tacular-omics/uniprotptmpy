"""Exceptions raised by uniprotptmpy."""

from __future__ import annotations


class UniprotPtmError(ValueError):
    """Base class for uniprotptmpy errors (e.g. a duplicate accession in a PtmDatabase).

    Also a ``ValueError`` (since 1.1), so ``except ValueError`` catches every uniprotptmpy error.
    """


class UniprotPtmParseError(UniprotPtmError, ValueError):
    """Malformed ptmlist.txt input or correction formula. Also a ValueError."""


class UniprotPtmKeyError(UniprotPtmError, KeyError):
    """``db[key]`` found no entry. Also a ``KeyError``; ``args[0]`` is the key looked up."""
