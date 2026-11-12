# Casa la Paz

Belegungsplan für das Familienhaus in Vinaròs. Eine HTML-Datei, Daten und Login in Supabase, ausgeliefert über GitHub Pages.

- `index.html` – die App. Gleiche Datei läuft auch als Werkbank im Claude-Artifact (dort mit Testdaten); Live-Modus nur auf den Adressen in `LIVE.hosts`.
- `supabase/setup.sql` – Tabellen, Regeln (Exklusivität, Freigabe, Verfall), Zugriffsrechte.
- `.github/workflows/` – täglicher Ping gegen das Einschlafen, wöchentliche verschlüsselte Sicherung.
- `EINRICHTUNG.md` – Schritt-für-Schritt-Anleitung.

Neue Version ausspielen: `APP_VERSION` in `index.html` und `version.json` gemeinsam hochzählen, committen. Geöffnete Apps laden sich beim nächsten Öffnen neu.
