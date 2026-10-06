# -*- coding: utf-8 -*-
"""執行期依賴補裝。

Streamlit Community Cloud 首次啟動若缺套件,會從 requirements.txt 安裝。
本檔保留原本在 etf_web.py 頂部的「import 失敗→pip install」保險邏輯。
"""

from __future__ import annotations

import subprocess
import sys


_RUNTIME_DEPS = ["streamlit", "pandas", "plotly", "openpyxl"]


def ensure_deps() -> None:
    """檢查 runtime 依賴,缺的用 pip 安裝。只在本機開發意外缺包時生效。"""
    for pkg in _RUNTIME_DEPS:
        try:
            __import__(pkg)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

    try:
        from streamlit_local_storage import LocalStorage  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "streamlit-local-storage", "-q"]
        )
