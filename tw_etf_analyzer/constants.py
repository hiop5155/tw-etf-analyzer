# -*- coding: utf-8 -*-
"""全域常數(無任何計算邏輯)。"""

# ── FinMind API ───────────────────────────────────────────────────────────────
FINMIND_API: str = "https://api.finmindtrade.com/api/v4/data"


# ── 現金假設 ──────────────────────────────────────────────────────────────────
# 視為真現金(活存/抽屜),不含貨幣市場收益;想納入短期收益請改用短期債券 ETF
CASH_RETURN: float = 0.0     # 年化報酬
CASH_VOL:    float = 0.0     # 年化波動度


# ── 稅費常數 ──────────────────────────────────────────────────────────────────
# 股利稅:合併課稅(income_tax_bracket − 8.5% 可抵減,抵減上限 80,000)
# 分離課稅固定 28%;系統自動選較低者
NHI_THRESHOLD: float            = 20_000    # 單筆股利 ≥ 此金額課二代健保補充保費
NHI_RATE: float                 = 0.0211
COMBINED_DEDUCTION_RATE: float  = 0.085
COMBINED_DEDUCTION_CAP: float   = 80_000
SEPARATE_TAX_RATE: float        = 0.28

# 預設手續費率(買進 0.1425% × 五折;賣出 = 手續費五折 + 證交稅 0.1%)
DEFAULT_BUY_FEE_RATE: float  = 0.0007125
DEFAULT_SELL_FEE_RATE: float = 0.0017125
