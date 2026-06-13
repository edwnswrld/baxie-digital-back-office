"""Synthetic, public-safe fixtures for the Baxie Digital Back Office.

Everything here is invented. No real client data, no Baxie schema. The synthetic
JobSource ships in the public repo so judges can run the whole crew offline.
"""

from fixtures.synthetic_source import SyntheticJobSource

__all__ = ["SyntheticJobSource"]
