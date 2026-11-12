// Server-Funktion "push" (Supabase Edge Function).
//   GET  → { publicKey }          öffentlicher VAPID-Schlüssel für die App
//   POST → verschickt alle fälligen Mitteilungen (idempotent, jede höchstens einmal):
//          neue Anfrage → Super-User, deren Freigabe fehlt;
//          fertig entschieden → die Person, die angefragt hat.
//          Die App ruft das nach jeder neuen Anfrage und jeder finalen Entscheidung auf.
//          Wer was bekommt, entscheidet die Datenbank (push_due).
import { send, type SendResult, type Vapid } from "./webpush.ts";

export type Row = {
  kind?: "request" | "confirmed" | "rejected";
  approvers?: string[]; decided_by?: string | null; reason?: string;
  booking_id: string; person_id: string; endpoint: string; p256dh: string; auth: string;
  booked_by: string; arrive: string; depart: string; high_season: boolean; open_count: number;
};
export type Deps = {
  rpc: (name: string, args: Record<string, unknown>) => Promise<unknown>;
  vapid: Vapid | null;
  fetcher?: typeof fetch;
  log?: (...a: unknown[]) => void;
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const MON_S = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."];
const parts = (s: string) => s.split("-").map(Number);
/** Gleiche Schreibweise wie fmtRange in index.html. */
export function fmtRange(a: string, b: string): string {
  const [ya, ma, da] = parts(a), [yb, mb, db] = parts(b);
  if (ya === yb && ma === mb) return `${da}.–${db}. ${MONTHS[ma - 1]} ${ya}`;
  if (ya === yb) return `${da}. ${MON_S[ma - 1]} – ${db}. ${MON_S[mb - 1]} ${ya}`;
  return `${da}. ${MON_S[ma - 1]} ${ya} – ${db}. ${MON_S[mb - 1]} ${yb}`;
}
const nightsOf = (a: string, b: string) => Math.round((Date.UTC(...(parts(b) as [number, number, number])) - Date.UTC(...(parts(a) as [number, number, number]))) / 864e5);

const andList = (a: string[]) => a.length > 1 ? `${a.slice(0, -1).join(", ")} und ${a[a.length - 1]}` : (a[0] ?? "");
const clip = (t: string, n: number) => t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t;

export function message(r: Row) {
  const n = nightsOf(r.arrive, r.depart);
  const range = fmtRange(r.arrive, r.depart);
  if (r.kind === "confirmed") {
    const who = r.approvers?.length ? r.approvers : r.decided_by ? [r.decided_by] : [];
    return {
      title: `Freigegeben: ${range}`,
      body: `${who.length ? `${andList(who)} ${who.length > 1 ? "haben" : "hat"} freigegeben. ` : ""}Dein Aufenthalt (${n === 1 ? "1 Nacht" : `${n} Nächte`}) ist bestätigt.`,
      badge: r.open_count, tag: `${r.booking_id}-d`, url: "./#anfragen",
    };
  }
  if (r.kind === "rejected") {
    const reason = (r.reason ?? "").trim();
    return {
      title: `Abgelehnt: ${range}`,
      body: `${r.decided_by ?? "Jemand"} hat abgelehnt${reason ? `: „${clip(reason, 140)}“` : "."}`,
      badge: r.open_count, tag: `${r.booking_id}-d`, url: "./#anfragen",
    };
  }
  return {
    title: `Neue Anfrage von ${r.booked_by}`,
    body: `${fmtRange(r.arrive, r.depart)} · ${n === 1 ? "1 Nacht" : `${n} Nächte`}${r.high_season ? " · Hochsaison" : ""}. Wartet auf deine Freigabe.`,
    badge: r.open_count,
    tag: r.booking_id,
    url: "./#anfragen",
  };
}

export async function sweep(d: Deps) {
  const log = d.log ?? console.log;
  if (!d.vapid) throw new Error("VAPID-Schlüssel fehlen");
  const rows = (await d.rpc("push_due", {})) as Row[];
  const results: (SendResult & { row: Row })[] = await Promise.all(
    rows.map(async (row) => ({ ...(await send(row, message(row), d.vapid!, d.fetcher)), row })),
  );
  const sent = new Map<string, { kind: string; booking_id: string; person_id: string }>();
  for (const r of results) {
    const kind = r.row.kind ?? "request";
    if (r.ok) sent.set(`${kind}|${r.row.booking_id}|${r.row.person_id}`, { kind, booking_id: r.row.booking_id, person_id: r.row.person_id });
  }
  const gone = results.filter((r) => r.gone).map((r) => r.endpoint);
  const ok = results.filter((r) => r.ok).map((r) => r.endpoint);
  for (const r of results) if (!r.ok) log(`push an ${r.row.person_id} (${new URL(r.endpoint).host}) fehlgeschlagen: ${r.status} ${r.detail ?? ""}`);
  if (results.length) await d.rpc("push_report", { p_sent: [...sent.values()], p_gone: gone, p_ok: ok });
  return { sent: sent.size, devices: ok.length, failed: results.length - ok.length - gone.length, gone: gone.length };
}

export function handler(d: Deps) {
  return async (req: Request): Promise<Response> => {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (!d.vapid) return json({ error: "Mitteilungen sind noch nicht eingerichtet." }, 503);
    if (req.method === "GET") return json({ publicKey: d.vapid.publicKey });
    if (req.method !== "POST") return json({ error: "Methode nicht erlaubt" }, 405);
    try {
      return json(await sweep(d));
    } catch (e) {
      (d.log ?? console.log)("push: Fehler", String(e));
      return json({ error: "Versand fehlgeschlagen" }, 500);
    }
  };
}

/** Abhängigkeiten aus den Umgebungsvariablen der Supabase Edge Function. */
export function envDeps(env: { get(k: string): string | undefined }): Deps {
  const url = env.get("SUPABASE_URL");
  let headers: Record<string, string> = {};
  const keys = env.get("SUPABASE_SECRET_KEYS");
  const secret = keys ? (JSON.parse(keys) as Record<string, string>).default : undefined;
  if (secret) headers = { apikey: secret };
  else {
    const legacy = env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    headers = { apikey: legacy, Authorization: `Bearer ${legacy}` };
  }
  const pub = env.get("VAPID_PUBLIC_KEY"), priv = env.get("VAPID_PRIVATE_KEY");
  return {
    vapid: pub && priv ? { publicKey: pub, privateKey: priv, subject: env.get("VAPID_SUBJECT") || "mailto:casalapaz.vinaros@gmail.com" } : null,
    async rpc(name, args) {
      const res = await fetch(`${url}/rest/v1/rpc/${name}`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(args),
      });
      const txt = await res.text();
      if (!res.ok) throw new Error(`${name}: ${res.status} ${txt.slice(0, 200)}`);
      return txt ? JSON.parse(txt) : null;
    },
  };
}
