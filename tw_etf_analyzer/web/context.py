# -*- coding: utf-8 -*-
"""AppContext — 集中傳遞全域狀態給每個 view,避免從 session_state 到處讀。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tw_etf_analyzer.core.tax import TaxFeeConfig

from tw_etf_analyzer.web.display import nominal_to_real_cagr, nominal_to_real_value


@dataclass
class AppContext:
    token:       str
    stock_id:    str
    monthly_dca: int
    close_full:  pd.Series
    tax_cfg:     TaxFeeConfig
    is_real:     bool       # 顯示模式 True=實質 / False=名目
    inflation:   float      # 小數;is_real 時才有意義

    # ── 顯示 helpers ──────────────────────────────────────────────────────────
    def display_value(self, nominal: float, years: float) -> float:
        """依全域設定把名目值折算為實質值(若切換實質模式)。"""
        if self.is_real and self.inflation > 0:
            return nominal_to_real_value(nominal, years, self.inflation)
        return nominal

    def display_cagr_pct(self, nominal_pct: float) -> float:
        """CAGR 名目 % → 實質 %(若切換實質模式)。"""
        if self.is_real and self.inflation > 0:
            return nominal_to_real_cagr(nominal_pct / 100, self.inflation) * 100
        return nominal_pct

    @property
    def real_sfx(self) -> str:
        """顯示用後綴,實質模式時附加「(實質)」。"""
        return "(實質)" if self.is_real else ""
