"""Reusable audit machinery, decoupled from any particular asset.

    asof      as-of grid construction with join tolerances and staleness columns
    holdout   purge, embargo, and the sealed-block look counter
    power     minimum detectable effect: compute it before committing a criterion
    validate  placebo, block-shuffle randomisation, staleness split

The order matters more than the parts: design, then power, then commitment, then
result. A criterion committed before its minimum detectable effect is known may be
unsatisfiable, and the project this was carried from discovered that after doing
the work rather than before.
"""

from . import asof, holdout, power, validate  # noqa: F401

__all__ = ["asof", "holdout", "power", "validate"]
