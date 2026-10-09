/**
 * 股票與 ETF 資料服務層 (整合前端本機快取與 Cloudflare Edge API)
 */

import { DividendRecord, PricePoint, StockInfo } from "../core/types";

// 本機快取有效時間: 12 小時
const CACHE_TTL_MS = 12 * 60 * 60 * 1000;

interface CacheEnvelope<T> {
  timestamp: number;
  data: T;
}

function getLocalCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(`tw_etf_${key}`);
    if (!raw) return null;
    const envelope: CacheEnvelope<T> = JSON.parse(raw);
    if (Date.now() - envelope.timestamp < CACHE_TTL_MS) {
      return envelope.data;
    }
  } catch (e) {
    // 忽略 parse 失敗
  }
  return null;
}

function setLocalCache<T>(key: string, data: T): void {
  try {
    const envelope: CacheEnvelope<T> = {
      timestamp: Date.now(),
      data,
    };
    localStorage.setItem(`tw_etf_${key}`, JSON.stringify(envelope));
  } catch (e) {
    // 若 localStorage 滿了則忽略
  }
}

export const API_BASE = (typeof window !== 'undefined' && window.location.pathname.startsWith('/calc')) ? '/calc/api' : '/api';

/**
 * 獲取還原除權息後的歷史收盤價序列
 */
export async function fetchAdjustedPrices(stockId: string): Promise<PricePoint[]> {
  const cleanId = stockId.toUpperCase().replace(".TW", "").trim();
  if (cleanId === "現金" || cleanId === "CASH") {
    return [];
  }

  const cacheKey = `prices_${cleanId}`;
  const cached = getLocalCache<PricePoint[]>(cacheKey);
  if (cached && cached.length > 0) {
    return cached;
  }

  const res = await fetch(`${API_BASE}/stock/adjusted?id=${encodeURIComponent(cleanId)}`);
  if (!res.ok) {
    throw new Error(`無法取得 ${cleanId} 股價資料 (${res.status})`);
  }

  const json = await res.json();
  const data: PricePoint[] = json.data || [];
  if (data.length > 0) {
    setLocalCache(cacheKey, data);
  }
  return data;
}

/**
 * 獲取歷年股利歷史明細
 */
export async function fetchDividends(stockId: string): Promise<DividendRecord[]> {
  const cleanId = stockId.toUpperCase().replace(".TW", "").trim();
  if (cleanId === "現金" || cleanId === "CASH") {
    return [];
  }

  const cacheKey = `dividends_${cleanId}`;
  const cached = getLocalCache<DividendRecord[]>(cacheKey);
  if (cached) {
    return cached;
  }

  const res = await fetch(`${API_BASE}/stock/dividends?id=${encodeURIComponent(cleanId)}`);
  if (!res.ok) {
    throw new Error(`無法取得 ${cleanId} 股利資料 (${res.status})`);
  }

  const json = await res.json();
  const data: DividendRecord[] = json.data || [];
  setLocalCache(cacheKey, data);
  return data;
}

/**
 * 獲取標的中文名稱與資訊
 */
export async function fetchStockInfo(stockId: string): Promise<StockInfo> {
  const cleanId = stockId.toUpperCase().replace(".TW", "").trim();
  if (cleanId === "現金" || cleanId === "CASH") {
    return { stock_id: "現金", stock_name: "現金 / 活存" };
  }

  const cacheKey = `info_${cleanId}`;
  const cached = getLocalCache<StockInfo>(cacheKey);
  if (cached) {
    return cached;
  }

  const res = await fetch(`${API_BASE}/stock/info?id=${encodeURIComponent(cleanId)}`);
  if (!res.ok) {
    return { stock_id: cleanId, stock_name: cleanId };
  }

  const json = await res.json();
  const info: StockInfo = {
    stock_id: cleanId,
    stock_name: json.stock_name || cleanId,
    industry_category: json.industry_category,
  };
  setLocalCache(cacheKey, info);
  return info;
}

