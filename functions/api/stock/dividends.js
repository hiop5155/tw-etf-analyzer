// Cloudflare Pages Function: /api/stock/dividends
// 代理 FinMind API，抓取個股或 ETF 歷年除權息紀錄

const FINMIND_API = "https://api.finmindtrade.com/api/v4/data";

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const stockId = (url.searchParams.get("id") || url.searchParams.get("stock_id") || "0050")
    .toUpperCase()
    .replace(".TW", "")
    .trim();

  // 1. 檢查 Cloudflare Edge Cache
  const cacheKey = new Request(url.toString(), request);
  const cache = caches.default;
  let cachedResponse = await cache.match(cacheKey);
  if (cachedResponse) {
    const newHeaders = new Headers(cachedResponse.headers);
    newHeaders.set("X-Cache", "HIT-EDGE");
    return new Response(cachedResponse.body, {
      status: cachedResponse.status,
      headers: newHeaders,
    });
  }

  const token = env.FINMIND_TOKEN || "";

  try {
    const divUrl = `${FINMIND_API}?dataset=TaiwanStockDividendResult&data_id=${encodeURIComponent(stockId)}&start_date=2000-01-01${token ? `&token=${encodeURIComponent(token)}` : ""}`;
    const res = await fetch(divUrl);
    const json = await res.json();

    if (!json.data || !Array.isArray(json.data)) {
      return new Response(JSON.stringify({ stock_id: stockId, data: [] }), {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

    const records = json.data
      .map((d) => {
        const cashDiv = parseFloat(d.stock_and_cache_dividend) || 0;
        const beforePrice = parseFloat(d.before_price) || 0;
        const afterPrice = parseFloat(d.after_price) || 0;
        const yieldPct = beforePrice > 0 ? (cashDiv / beforePrice) * 100 : 0;
        const year = d.date ? parseInt(d.date.substring(0, 4), 10) : 0;

        return {
          date: d.date,
          year,
          stock_id: d.stock_id,
          cash_dividend: cashDiv,
          before_price: beforePrice,
          after_price: afterPrice,
          yield_pct: Math.round(yieldPct * 100) / 100,
        };
      })
      .sort((a, b) => (a.date < b.date ? -1 : 1));

    const payload = {
      stock_id: stockId,
      total_records: records.length,
      data: records,
    };

    const response = new Response(JSON.stringify(payload), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=86400, s-maxage=86400",
        "Access-Control-Allow-Origin": "*",
        "X-Cache": "MISS",
      },
    });

    context.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch (err) {
    return new Response(
      JSON.stringify({ error: `獲取股利資料失敗: ${err.message}` }),
      {
        status: 500,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }
}
