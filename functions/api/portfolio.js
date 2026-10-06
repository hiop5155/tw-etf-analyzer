// Cloudflare Pages Function: /api/portfolio
import { verifyJwt } from './jwt.js';

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}

async function getAuthenticatedUserId(request, env) {
  const authHeader = request.headers.get('Authorization') || '';
  if (!authHeader) throw new Error('未授權');
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();
  const secret = env.JWT_SECRET || 'thisismysecretkey123456';
  const payload = await verifyJwt(token, secret);
  return payload.id || payload.userId;
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
  };

  try {
    const userId = await getAuthenticatedUserId(request, env);
    if (!env.DB) {
      return new Response(JSON.stringify({ exists: false, settings: null, warning: 'D1 not configured' }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    await env.DB.prepare(`
      CREATE TABLE IF NOT EXISTS user_portfolios (
        user_id TEXT PRIMARY KEY,
        settings_json TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `).run();

    const record = await env.DB.prepare('SELECT settings_json FROM user_portfolios WHERE user_id = ?')
      .bind(userId)
      .first();

    if (!record) {
      return new Response(JSON.stringify({ exists: false, settings: null }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    return new Response(JSON.stringify({ exists: true, settings: JSON.parse(record.settings_json) }), {
      status: 200,
      headers: corsHeaders,
    });
  } catch (err) {
    const status = err.message === '未授權' ? 401 : 500;
    return new Response(JSON.stringify({ error: err.message }), {
      status,
      headers: corsHeaders,
    });
  }
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
  };

  try {
    const userId = await getAuthenticatedUserId(request, env);
    if (!env.DB) {
      return new Response(JSON.stringify({ error: 'D1 database binding not found' }), {
        status: 500,
        headers: corsHeaders,
      });
    }

    const body = await request.json();
    const settingsJson = JSON.stringify(body);

    await env.DB.prepare(`
      CREATE TABLE IF NOT EXISTS user_portfolios (
        user_id TEXT PRIMARY KEY,
        settings_json TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `).run();

    await env.DB.prepare(`
      INSERT INTO user_portfolios (user_id, settings_json, updated_at)
      VALUES (?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(user_id) DO UPDATE SET
        settings_json = excluded.settings_json,
        updated_at = CURRENT_TIMESTAMP
    `).bind(userId, settingsJson).run();

    return new Response(JSON.stringify({ success: true, message: '投組設定已同步至 D1 資料庫' }), {
      status: 200,
      headers: corsHeaders,
    });
  } catch (err) {
    const status = err.message === '未授權' ? 401 : 500;
    return new Response(JSON.stringify({ error: err.message }), {
      status,
      headers: corsHeaders,
    });
  }
}
