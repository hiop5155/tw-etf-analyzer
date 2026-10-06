# -*- coding: utf-8 -*-
"""DEPRECATED — 已搬遷至 tw_etf_analyzer.pdf.builder。

此檔作為向後相容 shim,re-export 所有公開名稱。新程式請直接 import:
    from tw_etf_analyzer.pdf import PDFReportBuilder
"""

from tw_etf_analyzer.pdf.builder import (
    PDFReportBuilder, PDFSection,
    FONT_DIR, FONT_REGULAR, FONT_BOLD,
)
