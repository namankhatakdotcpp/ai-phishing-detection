"""Dataset composition stats for the Phase 7 report (counts by source/label)."""

from __future__ import annotations

import pandas as pd

from phishshield.data.schema import Sample


def dataset_stats(samples: list[Sample]) -> pd.DataFrame:
    """Return a `source`/`label`/`count` table describing `samples`.

    Raises ValueError on an empty list — an empty stats table would just
    be a confusing blank row in the report rather than a useful signal.
    """
    if not samples:
        raise ValueError("samples must be non-empty")

    rows = [{"source": s.source.value, "label": s.label} for s in samples]
    df = pd.DataFrame(rows)
    counts = df.groupby(["source", "label"], as_index=False).size()
    counts = counts.rename(columns={"size": "count"})
    return counts.sort_values(["source", "label"]).reset_index(drop=True)
