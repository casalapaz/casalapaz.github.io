# Casa la Paz

Belegungsplan für das Familienhaus in Vinaròs. Eine HTML-Datei, Daten und Login in Supabase, ausgeliefert über GitHub Pages.

- `index.html` – die App. Gleiche Datei läuft auch als Werkbank im Claude-Artifact (dort mit Testdaten); Live-Modus nur auf den Adressen in `LIVE.hosts`.
- `supabase/setup.sql` – Tabellen, Regeln (Exklusivität, Freigabe, Verfall), Zugriffsrechte, Mitteilungen (`push_due`). Einzelne Änderungen für bestehende Datenbanken: `supabase/migrate-*.sql`.
- `supabase/functions/push/` – Server-Funktion (Supabase Edge Function) für Web Push an Super-User; `sw.js` zeigt die Mitteilung und setzt den Zähler am App-Symbol.
- `.github/workflows/` – täglicher Ping gegen das Einschlafen, wöchentliche verschlüsselte Sicherung, Ausspielen der Server-Funktion `push`.
- `tests/` – `test_db.py` (Regeln in Postgres), `test_push.ts` (Deno: Verschlüsselung, VAPID, Versand gegen Postgres), `test_live.py` (Playwright gegen die echte index.html).
- `EINRICHTUNG.md` – Schritt-für-Schritt-Anleitung.

Neue Version ausspielen: `APP_VERSION` in `index.html` und `version.json` gemeinsam hochzählen, committen. Geöffnete Apps laden sich beim nächsten Öffnen neu.
