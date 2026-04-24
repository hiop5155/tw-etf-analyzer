# -*- coding: utf-8 -*-
"""DEPRECATED — etf_core.py 已搬遷至 tw_etf_analyzer.core。

此檔作為向後相容 shim,re-export 所有公開名稱。新程式請直接 import:
    from tw_etf_analyzer.core import ...

或從各 submodule:
    from tw_etf_analyzer.core.tax import TaxFeeConfig
    from tw_etf_analyzer.core.metrics import calc_risk_metrics
    ...
"""

from tw_etf_analyzer.constants import (
    CASH_RETURN, CASH_VOL,
    NHI_THRESHOLD, NHI_RATE,
    COMBINED_DEDUCTION_RATE, COMBINED_DEDUCTION_CAP, SEPARATE_TAX_RATE,
    DEFAULT_BUY_FEE_RATE, DEFAULT_SELL_FEE_RATE,
    FINMIND_API,
)
from tw_etf_analyzer.config import (
    CACHE_DIR, CACHE_TTL_H, load_token,
)
from tw_etf_analyzer.core import *  # noqa: F401,F403
