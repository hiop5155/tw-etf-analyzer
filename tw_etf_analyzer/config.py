# -*- coding: utf-8 -*-
"""Runtime 設定:路徑、Token、快取 TTL。

所有模組應從此取得路徑,避免用 `Path(__file__).parent` 造成 package 化後的錯誤定位。
"""

from __future__ import annotations

import os
from pathlib import Path


def _detect_project_root() -> Path:
    """以 cwd 為預設。允許 TWETF_ROOT 環境變數覆寫(部署時可用)。"""
    return Path(os.environ.get("TWETF_ROOT", Path.cwd())).resolve()


PROJECT_ROOT: Path = _detect_project_root()
CACHE_DIR:    Path = PROJECT_ROOT / "stock_cache"
FONT_DIR:     Path = PROJECT_ROOT / "fonts"
ENV_FILE:     Path = PROJECT_ROOT / ".env"

CACHE_TTL_H: int = 24

# 確保 cache 目錄存在(無副作用地建立)
CACHE_DIR.mkdir(exist_ok=True, parents=True)


# ── Token 載入 ────────────────────────────────────────────────────────────────
def load_token() -> str:
    """FINMIND_TOKEN 讀取優先順序:
    1. Streamlit Secrets(部署到 Streamlit Cloud 時)
    2. .env 檔(本機開發)
    3. 環境變數 FINMIND_TOKEN
    """
    # 1. Streamlit Secrets
    try:
        import streamlit as st
        token = st.secrets.get("FINMIND_TOKEN", "")
        if token:
            return token
    except Exception:
        pass

    # 2. .env 檔
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == "FINMIND_TOKEN":
                return val.strip().strip('"').strip("'")

    # 3. 環境變數
    return os.environ.get("FINMIND_TOKEN", "")
