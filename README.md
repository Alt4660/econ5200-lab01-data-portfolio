# econ5200-lab01-data-portfolio

# Data Quality Profiling — Big Mac Index

**Objective:** Diagnose and correct two common data-pipeline failures — a
sign error in a PPP valuation formula and survivorship bias from naive
missing-data handling — using The Economist's Big Mac Index panel.

**Methodology:**
- Computed implied PPP exchange rates and valuation percentages for the
  July 2024 cross-section; identified and fixed a reversed-subtraction bug
  that silently swapped every country's over/undervalued label.
- Diagnosed a listwise-deletion filter that dropped 32 of 57 countries to
  force a balanced panel, and showed the exclusion is driven by index
  membership timing (late joiners, early leavers), not by country
  characteristics.
- Quantified the resulting bias by comparing a balanced-only average
  against an all-available average across all 45 periods.
- Packaged the profiling, valuation, and missing-data logic into a
  reusable `data_utils.py` module and an interactive Streamlit dashboard.

**Key findings:**
- The corrected valuation confirms Switzerland (+41.8%), Uruguay (+24.3%),
  and Norway (+18.9%) as most overvalued, and Taiwan (−59.9%), Indonesia
  (−56.8%), and Egypt (−56.6%) as most undervalued.
- Restricting to countries with complete 45-period coverage overstates the
  global average Big Mac price by ~2.1% on average, and is directionally
  higher in 33 of 45 periods — a real, if modest, survivorship bias. A
  single-period Welch test (July 2024, n=25 vs. 29) does not reach
  significance (p=0.49); the evidence for the bias is its consistent sign
  across periods, not that one test.
