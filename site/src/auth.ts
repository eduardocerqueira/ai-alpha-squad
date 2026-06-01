// Self-contained magic-link auth for the Director dashboard.
//
// Flow: user submits an allow-listed email -> Worker emails a short-lived,
// HMAC-signed magic token -> clicking it sets a signed session cookie. The
// dashboard's data API requires that cookie. No DB: tokens are stateless and
// verified by signature + expiry (short TTL limits replay).

const SESSION_COOKIE = "director_session";
const MAGIC_TTL_SEC = 15 * 60; // 15 minutes
const SESSION_TTL_SEC = 7 * 24 * 60 * 60; // 7 days

export interface AuthEnv {
  AUTH_SECRET?: string;
  DIRECTOR_ALLOWED_EMAILS?: string;
}

// ---- base64url + bytes helpers ----------------------------------------------

const enc = new TextEncoder();

function b64urlFromBytes(buf: ArrayBuffer): string {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlFromString(s: string): string {
  return b64urlFromBytes(enc.encode(s).buffer as ArrayBuffer);
}

function stringFromB64url(s: string): string {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + pad;
  return atob(b64);
}

// ---- token sign / verify (compact HS256-style) ------------------------------

type TokenType = "magic" | "sess";

interface TokenPayload {
  sub: string; // email
  typ: TokenType;
  exp: number; // epoch seconds
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function signToken(secret: string, payload: TokenPayload): Promise<string> {
  const body = b64urlFromString(JSON.stringify(payload));
  const key = await hmacKey(secret);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(body));
  return `${body}.${b64urlFromBytes(sig)}`;
}

async function verifyToken(
  secret: string,
  token: string,
  typ: TokenType,
): Promise<TokenPayload | null> {
  const dot = token.indexOf(".");
  if (dot < 0) return null;
  const body = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const key = await hmacKey(secret);
  let ok = false;
  try {
    const sigBytes = Uint8Array.from(stringFromB64url(sig), (c) => c.charCodeAt(0));
    ok = await crypto.subtle.verify("HMAC", key, sigBytes, enc.encode(body));
  } catch {
    return null;
  }
  if (!ok) return null;
  let payload: TokenPayload;
  try {
    payload = JSON.parse(stringFromB64url(body));
  } catch {
    return null;
  }
  if (payload.typ !== typ) return null;
  if (typeof payload.exp !== "number" || payload.exp * 1000 < Date.now()) return null;
  return payload;
}

// ---- allowlist --------------------------------------------------------------

export function allowedEmails(env: AuthEnv): string[] {
  return (env.DIRECTOR_ALLOWED_EMAILS || "")
    .split(/[,\s]+/)
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

export function isAllowed(env: AuthEnv, email: string): boolean {
  return allowedEmails(env).includes(email.trim().toLowerCase());
}

// ---- magic token + session cookie -------------------------------------------

export async function createMagicToken(env: AuthEnv, email: string): Promise<string> {
  if (!env.AUTH_SECRET) throw new Error("AUTH_SECRET not configured");
  return signToken(env.AUTH_SECRET, {
    sub: email.trim().toLowerCase(),
    typ: "magic",
    exp: Math.floor(Date.now() / 1000) + MAGIC_TTL_SEC,
  });
}

export async function verifyMagicToken(env: AuthEnv, token: string): Promise<string | null> {
  if (!env.AUTH_SECRET) return null;
  const payload = await verifyToken(env.AUTH_SECRET, token, "magic");
  if (!payload || !isAllowed(env, payload.sub)) return null;
  return payload.sub;
}

export async function createSessionCookie(env: AuthEnv, email: string): Promise<string> {
  if (!env.AUTH_SECRET) throw new Error("AUTH_SECRET not configured");
  const token = await signToken(env.AUTH_SECRET, {
    sub: email.trim().toLowerCase(),
    typ: "sess",
    exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SEC,
  });
  return `${SESSION_COOKIE}=${token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${SESSION_TTL_SEC}`;
}

export function clearSessionCookie(): string {
  return `${SESSION_COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`;
}

function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(";")) {
    const idx = part.indexOf("=");
    if (idx < 0) continue;
    if (part.slice(0, idx).trim() === name) return part.slice(idx + 1).trim();
  }
  return null;
}

/** Returns the authenticated, still-allow-listed email, or null. */
export async function sessionEmail(env: AuthEnv, request: Request): Promise<string | null> {
  if (!env.AUTH_SECRET) return null;
  const token = readCookie(request, SESSION_COOKIE);
  if (!token) return null;
  const payload = await verifyToken(env.AUTH_SECRET, token, "sess");
  if (!payload || !isAllowed(env, payload.sub)) return null;
  return payload.sub;
}

export const MAGIC_TTL_MINUTES = MAGIC_TTL_SEC / 60;
