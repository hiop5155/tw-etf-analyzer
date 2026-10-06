// Lightweight WebCrypto-based JWT for Cloudflare Pages Functions

function base64UrlEncode(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  const bin = atob(str);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) {
    bytes[i] = bin.charCodeAt(i);
  }
  return new TextDecoder().decode(bytes);
}

export async function signJwt(payload, secret) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const encHeader = base64UrlEncode(JSON.stringify(header));
  const encPayload = base64UrlEncode(JSON.stringify(payload));
  const data = new TextEncoder().encode(`${encHeader}.${encPayload}`);

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, data);
  
  const sigBytes = new Uint8Array(signature);
  let sigBin = '';
  for (let i = 0; i < sigBytes.byteLength; i++) {
    sigBin += String.fromCharCode(sigBytes[i]);
  }
  const encSignature = btoa(sigBin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${encHeader}.${encPayload}.${encSignature}`;
}

export async function verifyJwt(token, secret) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid token structure');
  const [encHeader, encPayload, encSignature] = parts;
  const data = new TextEncoder().encode(`${encHeader}.${encPayload}`);

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify']
  );

  let rawSig = encSignature.replace(/-/g, '+').replace(/_/g, '/');
  while (rawSig.length % 4) rawSig += '=';
  const binSig = atob(rawSig);
  const sigBytes = new Uint8Array(binSig.length);
  for (let i = 0; i < binSig.length; i++) {
    sigBytes[i] = binSig.charCodeAt(i);
  }

  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data);
  if (!valid) throw new Error('Signature verification failed');

  return JSON.parse(base64UrlDecode(encPayload));
}
