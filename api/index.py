"""Vercel entry point. All real logic lives in ``uniprotptmpy.server.app``."""

from uniprotptmpy.server.app import app

__all__ = ["app"]
