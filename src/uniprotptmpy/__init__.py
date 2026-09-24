"""Python library for parsing and querying the UniProt PTM controlled vocabulary."""

from uniprotptmpy._download import download
from uniprotptmpy._ptmlist_writer import write_ptmlist
from uniprotptmpy._tabular import write_tsv
from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.errors import UniprotPtmError, UniprotPtmParseError
from uniprotptmpy.models import CrossReference, FeatureType, PtmEntry, TaxonomicRange
from uniprotptmpy.parser import load, parse_ptm_list

__version__ = "0.2.2"

__all__ = [
    "__version__",
    "CrossReference",
    "FeatureType",
    "PtmEntry",
    "TaxonomicRange",
    "UniprotPtmError",
    "UniprotPtmParseError",
    "PtmDatabase",
    "download",
    "load",
    "parse_ptm_list",
    "write_ptmlist",
    "write_tsv",
]
