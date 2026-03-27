import pytest

from uniprotptmpy import PtmDatabase, load


@pytest.fixture(scope="session")
def db() -> PtmDatabase:
    return load()
