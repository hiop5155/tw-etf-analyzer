# -*- coding: utf-8 -*-
"""
PDF 報告產生模組。

用法:
    from etf_pdf import PDFReportBuilder
    builder = PDFReportBuilder(title="台股績效分析報告")
    builder.add_cover(subtitle="...", meta={"股票代號": "0050", ...})
    builder.add_section("績效分析", ...)
    pdf_bytes = builder.build()
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


_HERE = Path(__file__).parent
FONT_DIR = _HERE / "fonts"
FONT_REGULAR = FONT_DIR / "NotoSansCJKtc-Regular.otf"
FONT_BOLD    = FONT_DIR / "NotoSansCJKtc-Bold.otf"


def _plotly_to_png_b64(fig, width: int = 900, height: int = 450) -> str:
    """Plotly figure → PNG base64(內嵌 <img src='data:image/png;base64,...'>)。"""
    import plotly.io as pio
    png_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
    return base64.b64encode(png_bytes).decode("ascii")


def _df_to_html(df, classes: str = "data-table") -> str:
    """DataFrame → HTML table(不含 index)。"""
    if df is None or (hasattr(df, "empty") and df.empty):
        return '<p class="muted">(無資料)</p>'
    return df.to_html(index=False, classes=classes, border=0, escape=False)


@dataclass
class PDFSection:
    title: str
    html:  str            # 任意 HTML 片段


@dataclass
class PDFReportBuilder:
    title:    str
    subtitle: str = ""
    meta:     dict = field(default_factory=dict)    # 封面摘要欄位
    sections: list[PDFSection] = field(default_factory=list)

    def add_section(self, title: str, html: str) -> "PDFReportBuilder":
        self.sections.append(PDFSection(title=title, html=html))
        return self

    def add_chart(self, title: str, fig, caption: str = "", width: int = 900, height: int = 450) -> "PDFReportBuilder":
        b64 = _plotly_to_png_b64(fig, width=width, height=height)
        html = f'<img class="chart" src="data:image/png;base64,{b64}" />'
        if caption:
            html += f'<p class="caption">{caption}</p>'
        self.sections.append(PDFSection(title=title, html=html))
        return self

    def add_metrics(self, title: str, metrics: list[tuple[str, str]]) -> "PDFReportBuilder":
        """輸入 [('指標名', '值'), ...] 輸出橫排卡片。"""
        cards = "".join(
            f'<div class="metric-card"><div class="metric-label">{k}</div>'
            f'<div class="metric-value">{v}</div></div>'
            for k, v in metrics
        )
        html = f'<div class="metrics-row">{cards}</div>'
        self.sections.append(PDFSection(title=title, html=html))
        return self

    def add_table(self, title: str, df) -> "PDFReportBuilder":
        self.sections.append(PDFSection(title=title, html=_df_to_html(df)))
        return self

    def add_text(self, title: str, text: str) -> "PDFReportBuilder":
        # 支援多行;簡單處理換行
        html = "".join(f"<p>{line}</p>" for line in text.splitlines() if line.strip())
        self.sections.append(PDFSection(title=title, html=html))
        return self

    # ── HTML 範本 ──────────────────────────────────────────────────────────
    def _css(self) -> str:
        reg_path = FONT_REGULAR.resolve().as_uri() if FONT_REGULAR.exists() else ""
        bold_path = FONT_BOLD.resolve().as_uri() if FONT_BOLD.exists() else ""
        return f"""
@font-face {{
    font-family: 'Noto Sans TC';
    src: url('{reg_path}') format('opentype');
    font-weight: normal;
}}
@font-face {{
    font-family: 'Noto Sans TC';
    src: url('{bold_path}') format('opentype');
    font-weight: bold;
}}
* {{ font-family: 'Noto Sans TC', sans-serif; }}
@page {{
    size: A4;
    margin: 2cm;
    @bottom-center {{
        content: "第 " counter(page) " / " counter(pages) " 頁";
        font-size: 9pt; color: #888;
    }}
}}
body {{
    margin: 0; padding: 0;
    color: #222;
    font-size: 10.5pt;
    line-height: 1.5;
}}
h1 {{ font-size: 22pt; color: #1f4f7a; margin: 0 0 6pt; }}
h2 {{ font-size: 15pt; color: #1f4f7a; border-bottom: 2pt solid #1f4f7a;
      padding-bottom: 3pt; margin-top: 18pt; }}
h3 {{ font-size: 12pt; color: #444; margin-top: 12pt; }}
p  {{ margin: 4pt 0; }}
.caption {{ color: #666; font-size: 9pt; margin-top: 2pt; }}
.muted   {{ color: #888; }}
.cover {{
    text-align: center;
    padding: 100pt 0 40pt;
    page-break-after: always;
}}
.cover h1 {{ font-size: 32pt; margin-bottom: 8pt; }}
.cover .subtitle {{ font-size: 14pt; color: #666; }}
.cover .meta {{
    margin: 40pt auto 0;
    padding: 16pt 24pt;
    width: 60%;
    text-align: left;
    background: #f4f6f8;
    border-left: 4pt solid #1f4f7a;
}}
.cover .meta-row {{ margin: 4pt 0; }}
.cover .meta-key {{ color: #666; display: inline-block; min-width: 120pt; }}
.cover .footer {{ position: absolute; bottom: 60pt; width: 100%;
                  text-align: center; color: #888; font-size: 9pt; }}
.section {{ page-break-inside: avoid; }}
.metrics-row {{
    display: flex;
    gap: 8pt;
    margin: 8pt 0;
    flex-wrap: wrap;
}}
.metric-card {{
    flex: 1 1 130pt;
    border: 1pt solid #ddd;
    border-radius: 3pt;
    padding: 8pt 12pt;
    background: #fafbfc;
}}
.metric-label {{ color: #666; font-size: 9pt; }}
.metric-value {{ color: #1f4f7a; font-size: 14pt; font-weight: bold; }}
.chart {{ width: 100%; display: block; margin: 8pt 0; }}
table.data-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0;
    font-size: 9.5pt;
}}
table.data-table th {{
    background: #1f4f7a;
    color: white;
    padding: 4pt 8pt;
    text-align: left;
    font-weight: bold;
}}
table.data-table td {{
    padding: 3pt 8pt;
    border-bottom: 1pt solid #eee;
}}
table.data-table tr:nth-child(even) td {{ background: #f9fafb; }}
"""

    def _cover_html(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        meta_html = "".join(
            f'<div class="meta-row"><span class="meta-key">{k}</span>{v}</div>'
            for k, v in self.meta.items()
        )
        return f"""
<div class="cover">
    <h1>{self.title}</h1>
    <div class="subtitle">{self.subtitle}</div>
    <div class="meta">{meta_html}</div>
    <div class="footer">由 tw-etf-analyzer 產生 · {now}</div>
</div>
"""

    def _body_html(self) -> str:
        parts = []
        for sec in self.sections:
            parts.append(f'<div class="section"><h2>{sec.title}</h2>{sec.html}</div>')
        return "\n".join(parts)

    def build(self) -> bytes:
        """產生 PDF bytes。"""
        import weasyprint

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{self.title}</title>
<style>{self._css()}</style>
</head><body>
{self._cover_html()}
{self._body_html()}
</body></html>"""

        return weasyprint.HTML(string=html, base_url=str(_HERE)).write_pdf()
