// Web Push ohne Bibliothek: VAPID (RFC 8292) + Verschlüsselung aes128gcm (RFC 8188/8291).
// Läuft in Deno (Supabase Edge Functions) und überall mit WebCrypto.

const enc = new TextEncoder();

export function b64u(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
export function unb64u(s: string): Uint8Array {
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}
// WebCrypto-Typen sind je nach TypeScript-Version strenger als nötig
const buf = (u: Uint8Array) => u as unknown as BufferSource;
function concat(...parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}
async function hkdf(salt: Uint8Array, ikm: Uint8Array, info: Uint8Array, bytes: number): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", buf(ikm), "HKDF", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: buf(salt), info: buf(info) }, key, bytes * 8));
}

export type Vapid = { publicKey: string; privateKey: string; subject: string };
export type Subscription = { endpoint: string; p256dh: string; auth: string };

/** Neues VAPID-Schlüsselpaar (base64url: öffentlich = 65 Byte unkomprimiert, privat = 32 Byte d). */
export async function generateVapidKeys(): Promise<{ publicKey: string; privateKey: string }> {
  const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]) as CryptoKeyPair;
  const raw = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey));
  const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);
  return { publicKey: b64u(raw), privateKey: jwk.d as string };
}

async function vapidHeader(endpoint: string, v: Vapid, now = Date.now()): Promise<string> {
  const pub = unb64u(v.publicKey);
  if (pub.length !== 65 || pub[0] !== 4) throw new Error("VAPID_PUBLIC_KEY ungültig");
  const key = await crypto.subtle.importKey("jwk", {
    kty: "EC", crv: "P-256", d: v.privateKey, x: b64u(pub.slice(1, 33)), y: b64u(pub.slice(33, 65)), ext: true,
  }, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const head = b64u(enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = b64u(enc.encode(JSON.stringify({
    aud: new URL(endpoint).origin,
    exp: Math.floor(now / 1000) + 12 * 3600, // Apple: höchstens 24 h
    sub: v.subject,
  })));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, buf(enc.encode(`${head}.${body}`))));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${v.publicKey}`;
}

/** Verschlüsselt eine Nachricht für ein Gerät (ein Datensatz, aes128gcm). */
export async function encrypt(payload: Uint8Array, sub: Subscription): Promise<Uint8Array> {
  const uaPublic = unb64u(sub.p256dh), authSecret = unb64u(sub.auth);
  const local = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]) as CryptoKeyPair;
  const asPublic = new Uint8Array(await crypto.subtle.exportKey("raw", local.publicKey));
  const peer = await crypto.subtle.importKey("raw", buf(uaPublic), { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: peer }, local.privateKey, 256));
  const ikm = await hkdf(authSecret, shared, concat(enc.encode("WebPush: info\0"), uaPublic, asPublic), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, enc.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, enc.encode("Content-Encoding: nonce\0"), 12);
  const aes = await crypto.subtle.importKey("raw", buf(cek), "AES-GCM", false, ["encrypt"]);
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: buf(nonce) }, aes, buf(concat(payload, new Uint8Array([2])))));
  const rs = new Uint8Array([0, 0, 16, 0]); // Datensatzgröße 4096
  return concat(salt, rs, new Uint8Array([asPublic.length]), asPublic, cipher);
}

export type SendResult = { endpoint: string; status: number; ok: boolean; gone: boolean; detail?: string };

/** Schickt eine Nachricht an ein Gerät. gone = Gerät abgemeldet oder Abo unbrauchbar → löschen.
 *  Ein falscher VAPID-Schlüssel wirft (betrifft alle Geräte, darf keine Abos löschen). */
export async function send(sub: Subscription, message: unknown, v: Vapid, fetcher: typeof fetch = fetch): Promise<SendResult> {
  const authorization = await vapidHeader(sub.endpoint, v);
  let body: Uint8Array;
  try { body = await encrypt(enc.encode(JSON.stringify(message)), sub); }
  catch (e) { return { endpoint: sub.endpoint, status: 0, ok: false, gone: true, detail: "Abo unbrauchbar: " + String(e) }; }
  let res: Response;
  try {
    res = await fetcher(sub.endpoint, {
      method: "POST",
      headers: {
        Authorization: authorization,
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        TTL: String(3 * 24 * 3600),
        Urgency: "high",
      },
      body: buf(body),
    });
  } catch (e) {
    return { endpoint: sub.endpoint, status: 0, ok: false, gone: false, detail: String(e) };
  }
  const detail = res.ok ? (await res.body?.cancel(), undefined) : (await res.text().catch(() => "")).slice(0, 300);
  return { endpoint: sub.endpoint, status: res.status, ok: res.ok, gone: res.status === 404 || res.status === 410, detail };
}
