/**
 * 台灣稅費模型: 股利所得稅 (合併 8.5% 抵減 vs 分離 28%) + 二代健保 (2.11%) + 券商手續費與證交稅
 * 1:1 精確對齊 tw_etf_analyzer/core/tax.py
 */

import {
  COMBINED_DEDUCTION_CAP,
  COMBINED_DEDUCTION_RATE,
  NHI_RATE,
  NHI_THRESHOLD,
  SEPARATE_TAX_RATE,
} from "./constants";
import { DividendRecord, PricePoint, TaxFeeConfig } from "./types";

/**
 * 對單筆股利金額，自動選擇「合併課稅 vs 分離課稅」較小者
 * 回傳 [有效稅率 (小數), 'combined' | 'separate']
 */
export function effectiveDividendTaxRate(
  dividendAmount: number,
  incomeTaxBracket: number
): [number, "combined" | "separate"] {
  if (dividendAmount <= 0) {
    return [0.0, "combined"];
  }

  const combinedTax = Math.max(
    0.0,
    dividendAmount * incomeTaxBracket -
      Math.min(
        dividendAmount * COMBINED_DEDUCTION_RATE,
        COMBINED_DEDUCTION_CAP
      )
  );

  const separateTax = dividendAmount * SEPARATE_TAX_RATE;

  if (combinedTax <= separateTax) {
    return [combinedTax / dividendAmount, "combined"];
  }
  return [SEPARATE_TAX_RATE, "separate"];
}

/**
 * 對一年份股利總額，回傳「實收到手比率」 (扣除所得稅 + 二代健保後 / 毛股利)
 */
export function dividendNetRatio(
  annualDividend: number,
  incomeTaxBracket: number
): number {
  if (annualDividend <= 0) return 1.0;
  const [taxRate] = effectiveDividendTaxRate(annualDividend, incomeTaxBracket);
  const nhi = annualDividend >= NHI_THRESHOLD ? NHI_RATE : 0.0;
  return Math.max(0.0, 1.0 - taxRate - nhi);
}

/**
 * 從歷史股利明細估算平均年現金殖利率 (小數)
 * 自動排除首年與尾年不完整資料
 */
export function avgAnnualDividendYield(
  dividends: DividendRecord[],
  series: PricePoint[]
): number {
  if (!dividends || dividends.length === 0 || !series || series.length === 0) {
    return 0.0;
  }

  // 1. 每年現金股利加總
  const annualSumMap: Record<number, number> = {};
  for (const d of dividends) {
    if (!annualSumMap[d.year]) annualSumMap[d.year] = 0;
    annualSumMap[d.year] += d.cash_dividend;
  }

  const years = Object.keys(annualSumMap).map(Number).sort();
  if (years.length === 0) return 0.0;

  const firstYr = parseInt(series[0].date.substring(0, 4), 10);
  const lastYr = parseInt(series[series.length - 1].date.substring(0, 4), 10);

  const completeYears = years.filter((y) => y !== firstYr && y !== lastYr);
  const targetYears = completeYears.length > 0 ? completeYears : years;

  const totalDiv = targetYears.reduce((sum, y) => sum + annualSumMap[y], 0);
  const avgDivPerShare = totalDiv / targetYears.length;

  const avgPrice =
    series.reduce((sum, p) => sum + p.close, 0) / series.length;
  if (avgPrice <= 0) return 0.0;

  return avgDivPerShare / avgPrice;
}

/**
 * 計算股利稅 + 二代健保造成的年化 CAGR 拖累 (小數)
 */
export function calcTaxDrag(
  dividendYield: number,
  portfolioValue: number,
  tax: TaxFeeConfig
): number {
  if (!tax.enabled || dividendYield <= 0 || portfolioValue <= 0) {
    return 0.0;
  }
  const annualDivEst = dividendYield * portfolioValue;
  const netRatio = dividendNetRatio(annualDivEst, tax.income_tax_bracket);
  return dividendYield * (1.0 - netRatio);
}

/**
 * 交易成本年化拖累
 */
export function calcFeeDrag(
  tax: TaxFeeConfig,
  turnoverPerYear: number = 0.0
): number {
  if (!tax.enabled) return 0.0;
  return tax.sell_fee_rate * turnoverPerYear;
}

/**
 * 套用買進手續費: 回傳 [實際買進金額, 手續費金額]
 */
export function applyBuyFee(
  amount: number,
  tax: TaxFeeConfig
): [number, number] {
  if (!tax.enabled) return [amount, 0.0];
  const fee = amount * tax.buy_fee_rate;
  return [amount - fee, fee];
}

/**
 * 套用賣出手續費 + 證交稅: 回傳 [實拿金額, 總費用]
 */
export function applySellFee(
  amount: number,
  tax: TaxFeeConfig
): [number, number] {
  if (!tax.enabled) return [amount, 0.0];
  const fee = amount * tax.sell_fee_rate;
  return [amount - fee, fee];
}
