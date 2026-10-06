// Cross-subdomain Single Sign-On (SSO) Cookie Manager for money-tracker.xyz & calc.money-tracker.xyz

export interface SharedUser {
  email: string;
  name: string;
  avatar?: string;
}

const COOKIE_TOKEN_NAME = "mt_auth_token";
const COOKIE_USER_NAME = "mt_auth_user";

function getCookieDomain(): string {
  const hostname = window.location.hostname;
  if (hostname.endsWith("money-tracker.xyz")) {
    return "; domain=.money-tracker.xyz";
  }
  return "";
}

export function setSharedAuth(token: string, user: SharedUser): void {
  const domainAttr = getCookieDomain();
  const maxAge = 60 * 60 * 24 * 30; // 30 天
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  
  document.cookie = `${COOKIE_TOKEN_NAME}=${encodeURIComponent(token)}; path=/; max-age=${maxAge}; SameSite=Lax${domainAttr}${secure}`;
  document.cookie = `${COOKIE_USER_NAME}=${encodeURIComponent(JSON.stringify(user))}; path=/; max-age=${maxAge}; SameSite=Lax${domainAttr}${secure}`;
}

export function getSharedAuth(): { token: string | null; user: SharedUser | null } {
  const cookies = document.cookie.split(";").reduce((acc, str) => {
    const [rawKey, ...rawVal] = str.trim().split("=");
    if (rawKey) {
      acc[rawKey] = decodeURIComponent(rawVal.join("="));
    }
    return acc;
  }, {} as Record<string, string>);

  const token = cookies[COOKIE_TOKEN_NAME] || null;
  let user: SharedUser | null = null;
  if (cookies[COOKIE_USER_NAME]) {
    try {
      user = JSON.parse(cookies[COOKIE_USER_NAME]);
    } catch {
      user = null;
    }
  }

  return { token, user };
}

export function clearSharedAuth(): void {
  const domainAttr = getCookieDomain();
  document.cookie = `${COOKIE_TOKEN_NAME}=; path=/; max-age=0; SameSite=Lax${domainAttr}`;
  document.cookie = `${COOKIE_USER_NAME}=; path=/; max-age=0; SameSite=Lax${domainAttr}`;
}
