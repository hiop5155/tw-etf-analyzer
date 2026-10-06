# -*- coding: utf-8 -*-
"""名目 ↔ 實質報酬換算 helpers。"""

from __future__ import annotations


def nominal_to_real_value(nominal: float, years: float, inflation: float) -> float:
    """將名目金額折現為今日購買力。"""
    if years <= 0 or inflation <= 0:
        return nominal
    return nominal / ((1 + inflation) ** years)


def nominal_to_real_cagr(nominal_cagr: float, inflation: float) -> float:
    """名目 CAGR → 實質 CAGR(Fisher 公式)。輸入/輸出皆為小數(非 %)。"""
    if inflation <= 0:
        return nominal_cagr
    return (1 + nominal_cagr) / (1 + inflation) - 1
