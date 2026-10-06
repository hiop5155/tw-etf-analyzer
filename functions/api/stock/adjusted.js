// Cloudflare Pages Function: /api/stock/adjusted
// 代理 FinMind API，抓取歷史股價與除權息/分割事件，並在邊緣計算還原收盤價與 24h 快取

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
    // 2. 平行呼叫 FinMind 三大數據集
    const priceUrl = `${FINMIND_API}?dataset=TaiwanStockPrice&data_id=${encodeURIComponent(stockId)}&start_date=2000-01-01${token ? `&token=${encodeURIComponent(token)}` : ""}`;
    const splitUrl = `${FINMIND_API}?dataset=TaiwanStockSplitPrice&data_id=${encodeURIComponent(stockId)}&start_date=2000-01-01${token ? `&token=${encodeURIComponent(token)}` : ""}`;
    const divUrl = `${FINMIND_API}?dataset=TaiwanStockDividendResult&data_id=${encodeURIComponent(stockId)}&start_date=2000-01-01${token ? `&token=${encodeURIComponent(token)}` : ""}`;

    const [priceRes, splitRes, divRes] = await Promise.all([
      fetch(priceUrl),
      fetch(splitUrl),
      fetch(divUrl),
    ]);

    const [priceJson, splitJson, divJson] = await Promise.all([
      priceRes.json(),
      splitRes.json(),
      divRes.json(),
    ]);

    if (!priceJson.data || priceJson.data.length === 0) {
      return new Response(
        JSON.stringify({ error: `查無 ${stockId} 股價資料，請確認股票代號` }),
        {
          status: 404,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
          },
        }
      );
    }

    // 3. 整理股價資料 (升冪排序)
    const rawPrices = priceJson.data
      .map((item) => ({
        date: item.date,
        close: parseFloat(item.close) || 0,
      }))
      .filter((item) => item.close > 0)
      .sort((a, b) => (a.date < b.date ? -1 : 1));

    // 4. 合併分割與除權息事件
    const events = [];
    if (splitJson.data && Array.isArray(splitJson.data)) {
      for (const s of splitJson.data) {
        if (s.before_price && s.after_price) {
          events.push({
            date: s.date,
            before: parseFloat(s.before_price),
            after: parseFloat(s.after_price),
            type: "split",
          });
        }
      }
    }

    if (divJson.data && Array.isArray(divJson.data)) {
      for (const d of divJson.data) {
        if (d.before_price && d.after_price) {
          events.push({
            date: d.date,
            before: parseFloat(d.before_price),
            after: parseFloat(d.after_price),
            type: "dividend",
          });
        }
      }
    }

    // 5. 執行除權息/分割回溯還原 (由最近事件往最遠事件調整)
    // 對於事件日期前的每一筆歷史價格，乘以 (after / before)
    events.sort((a, b) => (a.date < b.date ? 1 : -1));

    const adjustedSeries = rawPrices.map((item) => ({
      date: item.date,
      close: item.close,
    }));

    for (const ev of events) {
      const ratio = ev.after / ev.before;
      if (ratio > 0 && isFinite(ratio)) {
        for (let i = 0; i < adjustedSeries.length; i++) {
          if (adjustedSeries[i].date < ev.date) {
            adjustedSeries[i].close *= ratio;
          }
        }
      }
    }

    // 保留兩位小數避免浮點數過長
    const finalSeries = adjustedSeries.map((item) => ({
      date: item.date,
      close: Math.round(item.close * 100) / 100,
    }));

    const responsePayload = {
      stock_id: stockId,
      total_records: finalSeries.length,
      start_date: finalSeries[0]?.date || "",
      end_date: finalSeries[finalSeries.length - 1]?.date || "",
      events_count: events.length,
      data: finalSeries,
    };

    const response = new Response(JSON.stringify(responsePayload), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=86400, s-maxage=86400",
        "Access-Control-Allow-Origin": "*",
        "X-Cache": "MISS",
      },
    });

    // 寫入 Edge 快取
    context.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch (err) {
    return new Response(
      JSON.stringify({ error: `邊緣代理抓取失敗: ${err.message}` }),
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
