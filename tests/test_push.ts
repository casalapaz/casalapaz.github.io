// Prüft die Server-Funktion "push" lokal: Verschlüsselung gegen die Referenz-Bibliothek http_ece,
// VAPID-Signatur, und den kompletten Versand-Durchlauf gegen das lokale Postgres (gleiches setup.sql).
// Aufruf: deno run -A tests/test_push.ts   (lokales Postgres wie in tests/test_db.py)
import { createECDH, randomBytes } from "node:crypto";
import { Buffer } from "node:buffer";
import ece from "npm:http_ece@1.2.0";
import postgres from "npm:postgres@3.4.5";
import { b64u, encrypt, generateVapidKeys, send, unb64u } from "../supabase/functions/push/webpush.ts";
import { fmtRange, handler, message, type Row, sweep } from "../supabase/functions/push/handler.ts";

let ok = 0, fail = 0;
function check(name: string, cond: unknown, info: unknown = "") {
  if (cond) { ok++; console.log("  ok  ", name); } else { fail++; console.log("  FAIL", name, info); }
}

// Ein simuliertes iPhone: Schlüssel wie beim pushManager.subscribe()
function device(endpoint: string) {
  const dh = createECDH("prime256v1"); dh.generateKeys();
  const auth = randomBytes(16);
  return { dh, auth, sub: { endpoint, p256dh: b64u(new Uint8Array(dh.getPublicKey())), auth: b64u(new Uint8Array(auth)) } };
}
const decrypt = (d: ReturnType<typeof device>, body: Uint8Array) =>
  JSON.parse(Buffer.from(ece.decrypt(Buffer.from(body), { version: "aes128gcm", privateKey: d.dh, authSecret: d.auth })).toString("utf8"));

console.log("Verschlüsselung und Signatur");
const vapidKeys = await generateVapidKeys();
const vapid = { ...vapidKeys, subject: "mailto:casalapaz.vinaros@gmail.com" };
check("VAPID: öffentlicher Schlüssel 65 Byte, privat 32 Byte", unb64u(vapid.publicKey).length === 65 && unb64u(vapid.privateKey).length === 32);
const dev = device("https://web.push.apple.com/abc");
const msg = { title: "Neue Anfrage von Leon", body: "Grüße – äöü ☀", badge: 2 };
const body = await encrypt(new TextEncoder().encode(JSON.stringify(msg)), dev.sub);
check("http_ece entschlüsselt die Nachricht", JSON.stringify(decrypt(dev, body)) === JSON.stringify(msg));
check("Kopf: Datensatzgröße 4096, Schlüssel 65 Byte", body[16] === 0 && body[18] === 16 && body[20] === 65);

let captured: { url: string; headers: Headers; body: Uint8Array } | null = null;
const fake = (status: number) => (async (url: string | URL | Request, init?: RequestInit) => {
  captured = { url: String(url), headers: new Headers(init!.headers), body: init!.body as Uint8Array };
  return new Response(status === 201 ? "" : "nope", { status });
}) as typeof fetch;
const r1 = await send(dev.sub, msg, vapid, fake(201));
check("send: 201 = zugestellt", r1.ok && !r1.gone);
const h = captured!.headers;
check("Header: aes128gcm, TTL, Urgency", h.get("content-encoding") === "aes128gcm" && Number(h.get("ttl")) > 0 && h.get("urgency") === "high");
const m = /^vapid t=([^.]+)\.([^.]+)\.([^,]+), k=(.+)$/.exec(h.get("authorization")!);
check("Authorization im VAPID-Format", m && m[4] === vapid.publicKey, h.get("authorization"));
const claims = JSON.parse(new TextDecoder().decode(unb64u(m![2])));
check("JWT: aud = Herkunft des Push-Dienstes, sub = mailto, exp < 24 h", claims.aud === "https://web.push.apple.com" && claims.sub.startsWith("mailto:") && claims.exp - Date.now() / 1000 < 86400 && claims.exp > Date.now() / 1000, claims);
const pub = unb64u(vapid.publicKey);
const vkey = await crypto.subtle.importKey("jwk", { kty: "EC", crv: "P-256", x: b64u(pub.slice(1, 33)), y: b64u(pub.slice(33)) }, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
check("JWT-Signatur ES256 gültig", await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, vkey, unb64u(m![3]), new TextEncoder().encode(`${m![1]}.${m![2]}`)));
check("send: 410 = Gerät abgemeldet", (await send(dev.sub, msg, vapid, fake(410))).gone);
check("send: 500 = später erneut", !(await send(dev.sub, msg, vapid, fake(500))).ok && !(await send(dev.sub, msg, vapid, fake(500))).gone);
check("send: unbrauchbares Abo = löschen", (await send({ ...dev.sub, p256dh: "BAAA" }, msg, vapid, fake(201))).gone);
let threw = false; try { await send(dev.sub, msg, { ...vapid, privateKey: "AAAA" }, fake(201)); } catch { threw = true; }
check("send: falscher VAPID-Schlüssel wirft (löscht keine Abos)", threw);
check("send: Netzwerkfehler wirft nicht", (await send(dev.sub, msg, vapid, (() => Promise.reject(new Error("weg"))) as typeof fetch)).status === 0);

console.log("Texte");
check("fmtRange wie in der App", fmtRange("2027-07-17", "2027-07-25") === "17.–25. Juli 2027" && fmtRange("2027-07-28", "2027-08-03") === "28. Juli – 3. Aug. 2027" && fmtRange("2027-12-30", "2028-01-02") === "30. Dez. 2027 – 2. Jan. 2028");
const row = { booking_id: "x", person_id: "uli", endpoint: "", p256dh: "", auth: "", booked_by: "Leon", arrive: "2027-07-17", depart: "2027-07-18", high_season: true, open_count: 3 } as Row;
const mm = message(row);
check("Mitteilung: Titel, Text, Zähler, Ziel", mm.title === "Neue Anfrage von Leon" && mm.body === "17.–18. Juli 2027 · 1 Nacht · Hochsaison. Wartet auf deine Freigabe." && mm.badge === 3 && mm.url === "./#anfragen", mm);

console.log("Durchlauf gegen die Datenbank");
const sql = postgres({ host: "/tmp/pg", port: 5433, user: "postgres", database: "t1", onnotice: () => {} });
const asUser = (email: string, q: string, params: unknown[] = []) => sql.begin(async (tx) => {
  await tx`select set_config('request.jwt.claims', ${JSON.stringify({ email, role: "authenticated" })}, true)`;
  await tx`set local role authenticated`;
  return tx.unsafe(q, params as never[]);
});
const rpc = (name: string, args: Record<string, unknown>) => sql.begin(async (tx) => {
  await tx`set local role service_role`;
  if (name === "push_due") return (await tx`select coalesce(json_agg(t), '[]') as j from push_due() t`)[0].j;
  if (name === "push_report") { await tx`select push_report(${JSON.stringify(args.p_sent)}::text::jsonb, ${args.p_gone as string[]}::text[], ${args.p_ok as string[]}::text[])`; return null; }
  throw new Error("unbekannt " + name);
});
await sql`delete from bookings`; await sql`delete from push_subscriptions`;
for (const p of ["micha", "leon", "uli", "fanny", "karlina"]) await sql`update people set email = ${p + "@x.de"} where id = ${p}`;
const phones: Record<string, ReturnType<typeof device>> = {};
for (const [who, ep] of [["micha", "https://web.push.apple.com/m"], ["uli", "https://web.push.apple.com/u"], ["fanny", "https://web.push.apple.com/f-weg"], ["fanny", "https://web.push.apple.com/f"]]) {
  const d = device(ep); phones[ep] = d;
  await asUser(`${who}@x.de`, "select save_push_subscription($1, $2, $3)", [d.sub.endpoint, d.sub.p256dh, d.sub.auth]);
}
const inbox: Record<string, { title: string; body: string; badge: number; tag: string }[]> = {};
let flaky = true;
const pushService = (async (url: string | URL | Request, init?: RequestInit) => {
  const ep = String(url);
  if (ep.endsWith("f-weg")) return new Response("", { status: 410 });
  if (ep.endsWith("/u") && flaky) { flaky = false; return new Response("busy", { status: 503 }); }
  (inbox[ep] ??= []).push(decrypt(phones[ep], init!.body as Uint8Array));
  return new Response("", { status: 201 });
}) as typeof fetch;
const deps = { rpc, vapid, fetcher: pushService, log: () => {} };

await asUser("leon@x.de", "select create_booking('2027-10-20', '2027-10-24')");
let res = await sweep(deps);
check("Leon fragt an: Fanny bekommt sie, Uli-Server kurz weg, Michas Familie nichts", res.sent === 1 && res.gone === 1 && res.failed === 1 && !inbox["https://web.push.apple.com/m"], res);
const f = inbox["https://web.push.apple.com/f"]?.[0];
check("Fanny: Titel, Text, Zähler 1", f && f.title === "Neue Anfrage von Leon" && f.body.startsWith("20.–24. Oktober 2027 · 4 Nächte.") && f.badge === 1, f);
check("Abgemeldetes Gerät gelöscht", (await sql`select count(*)::int as n from push_subscriptions where endpoint like '%f-weg'`)[0].n === 0);
res = await sweep(deps);
check("Zweiter Durchlauf: nur Uli (nachgeholt), Fanny nicht doppelt", res.sent === 1 && inbox["https://web.push.apple.com/u"]?.length === 1 && inbox["https://web.push.apple.com/f"].length === 1, res);
res = await sweep(deps);
check("Dritter Durchlauf: nichts mehr", res.sent === 0 && res.devices === 0, res);
await asUser("karlina@x.de", "select create_booking('2027-07-05', '2027-07-08')");
await sweep(deps);
const fm = inbox["https://web.push.apple.com/m"]?.[0], fu = inbox["https://web.push.apple.com/u"][1], ff = inbox["https://web.push.apple.com/f"][1];
check("Hochsaison-Anfrage von Karlina: Micha, Uli (eigene Familie) und Fanny", fm && fu && ff && [fm, fu, ff].every((x) => x.title === "Neue Anfrage von Karlina" && x.body.includes("Hochsaison")), [fm, fu, ff]);
check("Zähler je Person: Micha 1, Uli 2 (Leon + Karlina), Fanny 2", fm?.badge === 1 && fu?.badge === 2 && ff?.badge === 2, [fm?.badge, fu?.badge, ff?.badge]);

console.log("HTTP");
const hd = handler(deps);
const g = await hd(new Request("http://x/push"));
check("GET liefert öffentlichen Schlüssel", (await g.json()).publicKey === vapid.publicKey && g.headers.get("access-control-allow-origin") === "*");
check("OPTIONS (CORS) 204", (await hd(new Request("http://x/push", { method: "OPTIONS" }))).status === 204);
const p = await hd(new Request("http://x/push", { method: "POST" }));
check("POST verschickt (nichts Neues)", p.status === 200 && (await p.json()).sent === 0);
const off = handler({ ...deps, vapid: null });
check("Ohne Schlüssel: 503 mit Hinweis", (await off(new Request("http://x/push"))).status === 503);
const broken = handler({ ...deps, rpc: () => Promise.reject(new Error("db weg")) });
check("Datenbankfehler: 500 ohne Details", (await broken(new Request("http://x/push", { method: "POST" }))).status === 500);

await sql`delete from bookings`; await sql`delete from push_subscriptions`;
await sql.end();
console.log(`\n${ok} ok, ${fail} fehlgeschlagen`);
Deno.exit(fail ? 1 : 0);
