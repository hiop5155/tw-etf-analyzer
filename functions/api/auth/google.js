// Cloudflare Pages Function: /api/auth/google
import { signJwt } from '../jwt.js';

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
  };

  try {
    const { credential } = await request.json();
    if (!credential) {
      return new Response(JSON.stringify({ error: '缺少 Google 憑證' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // 驗證 Google ID Token
    const resp = await fetch(`https://oauth2.googleapis.com/tokeninfo?id_token=${credential}`);
    if (!resp.ok) {
      return new Response(JSON.stringify({ error: 'Google 驗證無效' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    const gUser = await resp.json();
    const email = (gUser.email || '').toLowerCase().trim();
    const googleId = gUser.sub;
    const name = gUser.name || email.split('@')[0];
    const avatar = gUser.picture || '';

    let userId = googleId;

    // 若有綁定 D1，更新或寫入 users 表格
    if (env.DB) {
      try {
        await env.DB.prepare(`
          CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            google_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            avatar_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `).run();

        const existing = await env.DB.prepare('SELECT id FROM users WHERE email = ? OR google_id = ?')
          .bind(email, googleId)
          .first();

        if (existing) {
          userId = existing.id;
          await env.DB.prepare(
            'UPDATE users SET google_id = ?, name = COALESCE(NULLIF(?, ""), name), avatar_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
          ).bind(googleId, name, avatar, userId).run();
        } else {
          userId = crypto.randomUUID();
          await env.DB.prepare(
            'INSERT INTO users (id, google_id, email, name, avatar_url) VALUES (?, ?, ?, ?, ?)'
          ).bind(userId, googleId, email, name, avatar).run();
        }
      } catch (dbErr) {
        console.warn('D1 user sync warning:', dbErr.message);
      }
    }

    const secret = env.JWT_SECRET || 'thisismysecretkey123456';
    const token = await signJwt({ id: userId, email }, secret);

    return new Response(JSON.stringify({ token, email, name, avatar }), {
      status: 200,
      headers: corsHeaders,
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: '登入失敗: ' + err.message }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}
