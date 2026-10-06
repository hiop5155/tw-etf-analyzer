/**
 * 全域財務與計算常數
 */

// 現金假設: 視為無風險真現金 (活存)，年化報酬 0%，波動度 0%
export const CASH_RETURN = 0.0;
export const CASH_VOL = 0.0;

// 稅費常數 (台灣稅制)
export const NHI_THRESHOLD = 20_000; // 單筆股利 ≥ 2 萬元課徵二代健保補充保費
export const NHI_RATE = 0.0211; // 二代健保補充保費費率 2.11%
export const COMBINED_DEDUCTION_RATE = 0.085; // 綜合所得稅股利抵減率 8.5%
export const COMBINED_DEDUCTION_CAP = 80_000; // 股利可抵減稅額上限 8 萬元
export const SEPARATE_TAX_RATE = 0.28; // 分離課稅固定 28%

// 預設台股交易手續費率 (買進 0.1425% × 5折; 賣出 = 手續費5折 + ETF證交稅 0.1%)
export const DEFAULT_BUY_FEE_RATE = 0.0007125;
export const DEFAULT_SELL_FEE_RATE = 0.0017125;

// 常用台股 ETF 預設組合
export interface PresetPortfolio {
  name: string;
  desc: string;
  holdings: { id: string; name: string; weight: number }[];
}

export const PRESET_PORTFOLIOS: PresetPortfolio[] = [
  {
    name: "0050 單一持有 (大盤核心)",
    desc: "100% 台灣五十，複製台股市值龍頭企業整體成長",
    holdings: [{ id: "0050", name: "元大台灣50", weight: 100 }],
  },
  {
    name: "保守配息型 (股債均衡)",
    desc: "高股息龍頭搭配長期美債與現金，降低退休提領波動度",
    holdings: [
      { id: "0056", name: "元大高股息", weight: 40 },
      { id: "00878", name: "國泰永續高股息", weight: 30 },
      { id: "00679B", name: "元大美債20年", weight: 20 },
      { id: "現金", name: "活存/流動資金", weight: 10 },
    ],
  },
  {
    name: "成長平衡型 (市值 + 高息)",
    desc: "兼顧市值成長動能與季配高股息現金流",
    holdings: [
      { id: "006208", name: "富邦台50", weight: 50 },
      { id: "00713", name: "元大台灣高息低波", weight: 30 },
      { id: "00687B", name: "國泰20年美債", weight: 20 },
    ],
  },
  {
    name: "高息低波防禦型",
    desc: "極低回撤的高息策略，適合進入退休期的現金流規劃",
    holdings: [
      { id: "00713", name: "元大台灣高息低波", weight: 50 },
      { id: "00878", name: "國泰永續高股息", weight: 30 },
      { id: "現金", name: "現金 / 活存", weight: 20 },
    ],
  },
];
