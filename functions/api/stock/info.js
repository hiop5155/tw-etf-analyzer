// Cloudflare Pages Function: /api/stock/info
// 查詢股票/ETF 中文名稱與資訊，快取 7 天

const FINMIND_API = "https://api.finmindtrade.com/api/v4/data";

// 常見台股標的內建快取映射，秒回無延遲
const PRESET_NAMES = {
  "0050": "元大台灣50",
  "0056": "元大高股息",
  "00878": "國泰永續高股息",
  "006208": "富邦台灣采吉50",
  "00713": "元大台灣高息低波",
  "00919": "群益台灣精選高息",
  "00929": "復華台灣科技優息",
  "00679B": "元大美債20年",
  "00687B": "國泰20年美債",
  "00720B": "元大投資級公司債",
  "00751B": "元大AAA至A公司債",
  "2330": "台積電",
  "2317": "鴻海",
  "2454": "聯發科",
  "現金": "現金 / 活存",
  "CASH": "現金 / 活存",
};

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const stockId = (url.searchParams.get("id") || url.searchParams.get("stock_id") || "0050")
    .toUpperCase()
    .replace(".TW", "")
    .trim();

  if (PRESET_NAMES[stockId]) {
    return new Response(
      JSON.stringify({
        stock_id: stockId,
        stock_name: PRESET_NAMES[stockId],
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=604800, s-maxage=604800",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }

  // 1. 檢查 Edge Cache
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
    const infoUrl = `${FINMIND_API}?dataset=TaiwanStockInfo&data_id=${encodeURIComponent(stockId)}${token ? `&token=${encodeURIComponent(token)}` : ""}`;
    const res = await fetch(infoUrl);
    const json = await res.json();

    let stockName = stockId;
    let industry = "";
    if (json.data && Array.isArray(json.data) && json.data.length > 0) {
      stockName = json.data[0].stock_name || stockId;
      industry = json.data[0].industry_category || "";
    }

    const payload = {
      stock_id: stockId,
      stock_name: stockName,
      industry_category: industry,
    };

    const response = new Response(JSON.stringify(payload), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=604800, s-maxage=604800",
        "Access-Control-Allow-Origin": "*",
        "X-Cache": "MISS",
      },
    });

    context.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch (err) {
    return new Response(
      JSON.stringify({
        stock_id: stockId,
        stock_name: stockId,
        error: err.message,
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }
}
