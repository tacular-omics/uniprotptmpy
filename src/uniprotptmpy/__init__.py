"""Python library for parsing and querying the UniProt PTM controlled vocabulary."""

from importlib.metadata import version

from uniprotptmpy._download import download
from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.models import CrossReference, FeatureType, PtmEntry, TaxonomicRange
from uniprotptmpy.parser import load, parse_ptm_list

__version__ = version("uniprotptmpy")

__all__ = [
    "__version__",
    "CrossReference",
    "FeatureType",
    "PtmEntry",
    "TaxonomicRange",
    "PtmDatabase",
    "download",
    "load",
    "parse_ptm_list",
]
