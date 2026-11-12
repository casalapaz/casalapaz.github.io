# Casa la Paz – Einrichtung der Live-App

**Stand:** 12.11.2026 · App-Version 4.4.0 (live)
**Für:** Leon (einmalig)
**Dauer:** ca. 60–75 Minuten am Laptop, danach 10 Minuten pro Familienmitglied am iPhone
**Kosten:** 0 € (GitHub Free, Supabase Free, Gmail)

> **So liest du diese Anleitung:** Arbeite die Teile **A bis F, dann I, dann G und H** ab. Jeder Schritt endet mit **✅ Fertig, wenn …** – erst dann weiter. Menünamen in Supabase und GitHub können leicht abweichen; gemeint ist immer der naheliegende Punkt. Hängst du irgendwo, schick Claude einen Screenshot.

---

## Überblick

| Teil | Was | Wer | Dauer |
|---|---|---|---|
| **0** | Vier Entscheidungen treffen | Leon | ✅ erledigt |
| **A** | Notizzettel vorbereiten | Leon | 2 Min. |
| **B** | Gmail-Konto für den Code-Versand + Weiterleitung | Leon | 12 Min. |
| **C** | Supabase: Datenbank und Login | Leon | 25 Min. |
| **D** | GitHub: Konto, Organisation, Repo, mit Claude verbinden | Leon | 15 Min. |
| **E** | Claude schaltet die App scharf | **Claude** | 10 Min. |
| **F** | GitHub Pages und Wartungs-Jobs aktivieren | Leon | 10 Min. |
| **I** | Mitteilungen einrichten (neu in 4.4.0) – **vor G** | Leon | 10 Min. |
| **G** | Testlauf mit zwei Personen (inkl. Mitteilung) | Leon + Micha | 15 Min. |
| **H** | Familie aufs iPhone bringen | Leon | 10 Min. pro Person |

**Begriffe in einem Satz:**
- **Supabase** – die Datenbank im Internet. Dort liegen Personen und Buchungen, dort prüft der Server alle Regeln, und von dort kommen die Login-Codes.
- **GitHub** – speichert die App-Dateien. **Repo** = der Projektordner der App mit allen Dateien und ihrer Änderungsgeschichte.
- **GitHub Pages** – macht aus dem Repo die Web-Adresse der App: `https://casalapaz.github.io`.
- **Öffentliches Repo** – jeder kann den *Code* ansehen, aber nicht ändern. Die *Buchungen* sieht nur, wer eingeloggt ist. Im Code steht nichts Geheimes.

---

## Teil 0 – Entscheidungen ✅ erledigt (12.11.)

| # | Frage | Entscheidung | Status |
|---|---|---|---|
| 1 | Eigenes Profil für deine Mutter? | **Nein.** Sie läuft über Michas Buchungen. | so eingerichtet |
| 2 | Wie lange bleibt eine Anfrage offen? | **21 Tage** – in der Hochsaison und in normalen Wochen. Danach verfällt sie, wenn die nötigen Freigaben fehlen. | eingebaut (4.2.0) |
| 3 | Gelten die vier gesetzten Regeln? (Verfall offener Anfragen; erste Entscheidung je Person gilt; Ablehnen darf jeder Super-User; Verlängern braucht neue Freigabe) | **Ja.** | gilt |
| 4 | Grenzen pro Aufenthalt | **Höchstens 31 Nächte am Stück** (= jeder Kalendermonat komplett buchbar). Max. 12 Freunde, Notiz max. 500 Zeichen bleiben. | eingebaut (4.2.0) |

---

## Teil A – Notizzettel vorbereiten

Während der Einrichtung entstehen zehn Werte. Lege dafür **einen Eintrag „Casa la Paz“ in deinem Passwortmanager** an und trage sie dort ein, sobald sie entstehen.

| # | Wert | Entsteht in | Geheim? | An Claude schicken? |
|---|---|---|---|---|
| 1 | Gmail-Adresse für die App | B1 | nein | nein |
| 2 | Gmail-App-Passwort (16 Zeichen) | B3 | **ja** | **nein** |
| 3 | Supabase-Datenbank-Passwort | C1 | **ja** | **nein** |
| 4 | Supabase **Project URL** (`https://….supabase.co`) | C7 | nein | **ja** |
| 5 | Supabase **Publishable key** (`sb_publishable_…`) | C7 | nein, ist öffentlich | **ja** |
| 6 | Supabase **Secret key** (`sb_secret_…`) | C7 | **ja** | **nein** |
| 7 | **GitHub-Organisation** (z. B. `casalapaz`) | D1b | nein | **ja** |
| 8 | **Sicherungs-Passwort** (neu ausdenken, lang) | F3 | **ja** | **nein** |
| 9 | **Supabase-Konto-Passwort** (Login bei supabase.com) | C1 | **ja** | **nein** |
| 10 | **Supabase-Zugangs-Token** (`sbp_…`) | I2 | **ja** | **nein** |

> ⚠️ **Geheime Werte gehören nie in einen Chat** – auch nicht zu Claude. Sie werden nur in Supabase bzw. GitHub eingetragen.

✅ **Fertig, wenn** der Eintrag im Passwortmanager existiert.

---

## Teil B – Gmail-Konto für den Code-Versand (10 Min.)

**Warum:** Die App schickt jeder Person beim Anmelden einen 6-stelligen Code per E-Mail. Supabase selbst schafft nur 2 Mails pro Stunde, deshalb läuft der Versand über ein eigenes Gmail-Konto. **Deine Hotmail-Adresse geht nicht:** Microsoft erlaubt seit September 2024 keinen Versand per Passwort mehr aus fremden Programmen.

**B1. Konto anlegen**
1. accounts.google.com → *Konto erstellen* → *Für mich persönlich*.
2. Adresse z. B. `casalapaz.vinaros@gmail.com` (falls vergeben: Variante wählen).
3. → Notizzettel **#1**.

**B2. 2-Faktor-Anmeldung einschalten** (Voraussetzung für Schritt B3)
1. myaccount.google.com → *Sicherheit* → *Bestätigung in zwei Schritten* → einschalten, deine Handynummer hinterlegen.

**B3. App-Passwort erzeugen**
1. myaccount.google.com/apppasswords öffnen (im neuen Konto angemeldet).
2. Name: `Casa la Paz` → *Erstellen*.
3. Das 16-stellige Passwort kopieren (Leerzeichen weglassen) → Notizzettel **#2**. Es wird nur einmal angezeigt.

**B4. Weiterleitung an deine Hotmail** (damit Warnungen von Supabase bei dir ankommen)
1. Im neuen Gmail-Konto: Zahnrad → *Alle Einstellungen aufrufen* → *Weiterleitung und POP/IMAP*.
2. *Weiterleitungsadresse hinzufügen* → deine Hotmail-Adresse → Bestätigungscode aus der Hotmail eingeben.
3. *Kopie eingehender Nachrichten weiterleiten an* wählen, *Gmail-Kopie im Posteingang behalten* → *Änderungen speichern*.

ℹ️ Die Login-Codes der Familie werden nur *verschickt* und landen nicht bei dir. Bei dir kommen nur Warnungen und Rückläufer an (z. B. eine falsch geschriebene Familienadresse).

✅ **Fertig, wenn** #1 und #2 im Passwortmanager stehen und die Weiterleitung aktiv ist.

---

## Teil C – Supabase: Datenbank und Login (25 Min.)

**C1. Projekt anlegen**
1. supabase.com → *Start your project* → *Sign up* mit **der App-Gmail-Adresse (#1)** und einem neuen Passwort (→ #9). **Nicht** „Continue with GitHub“. Bestätigungsmail im Gmail-Konto anklicken.
   *Warum das App-Konto:* Supabase erlaubt pro Konto nur 2 kostenlose aktive Projekte – so bleibt dein privates Kontingent frei, und Casa la Paz lässt sich später als Paket übergeben.
2. *New project*:

| Feld | Auswahl |
|---|---|
| Organization | Casa La Paz Vinaros (FREE) |
| GitHub (optional) | **nicht verbinden** |
| Project name | `casa-la-paz` |
| Database password | *Generate a password* → kopieren → Notizzettel **#3** |
| Region | *Need a specific region?* → **Central EU (Frankfurt)** |
| ☑ Enable Data API | **an** (darüber spricht die App mit der Datenbank) |
| ☐ Automatically expose new tables | **aus** (das SQL vergibt alle Rechte ausdrücklich) |
| ☑ Enable automatic RLS | **an** (Sicherheitsnetz: neue Tabellen starten gesperrt) |

3. *Create new project* → 1–2 Minuten warten.

✅ **Fertig, wenn** das Projekt-Dashboard ohne Ladebalken erscheint.

**C2. Datenbank einrichten**
1. Links *SQL Editor* → *New query*.
2. Den **kompletten** Inhalt der Datei `supabase/setup.sql` einfügen (aus dem Repo bzw. der ZIP; liegt auch im Projekt-Dokument `claude/repo-dateien.md`).
3. *Run* drücken.

✅ **Fertig, wenn** unten „Success. No rows returned“ steht.
❌ **Fehler?** Text kopieren und Claude schicken. Betrifft der Fehler `auth.users`: siehe Problemlösung P3.

**C3. E-Mail-Adressen der Familie eintragen**
1. Links *Table Editor* → Tabelle **`people`**.
2. Die zehn Personen sind schon angelegt. Bei jeder in die Spalte **`email`** die Adresse eintragen – **komplett kleingeschrieben**, ohne Leerzeichen:

| Familie | Personen | Super-User |
|---|---|---|
| Michas Familie | Micha, Leon, Marilen, Olivia | Micha |
| Ulis Familie | Uli, Kaspar, Karlina, Kajus | Uli |
| Fannys Familie | Fanny, Merle | Fanny |

3. Nichts anderes ändern (`id`, `stamm`, `is_super` bleiben, wie sie sind).

✅ **Fertig, wenn** alle zehn Zeilen eine E-Mail haben.
ℹ️ Nur wer hier mit E-Mail steht, kann sich anmelden. Jede andere Adresse bekommt „nicht freigeschaltet“.

**C4. Login-Einstellungen prüfen**
1. Links *Authentication* → *Sign In / Providers* → *Email*:
   - Email aktiviert lassen
   - **Email OTP Length: 6**
   - **Email OTP Expiration: 3600** (Sekunden)
   - *Save*
2. Auf derselben Seite unter *User Signups* so lassen: **Allow new users to sign up: an** (sonst bekommt beim ersten Login niemand einen Code – Fremde blockiert die Datenbank), **Confirm email: an**, *Allow anonymous sign-ins* und *Allow manual linking*: **aus**.

✅ **Fertig, wenn** OTP-Länge 6 und Ablauf 3600 gespeichert sind.

**C5. Mailversand über Gmail**
⚠️ **Reihenfolge:** Supabase lässt die Mail-Vorlagen erst bearbeiten, wenn SMTP eingerichtet ist. Im Aufklappmenü neben „Set up SMTP“ **nichts** wählen (kein „Upgrade to Pro“, kein „Send Email hook“).

1. *Authentication* → *Emails* → Knopf **„Set up SMTP“** bzw. Reiter *SMTP Settings* → **Enable Custom SMTP** einschalten:

| Feld | Wert |
|---|---|
| Sender email | Gmail-Adresse (#1) |
| Sender name | `Casa la Paz` |
| Host | `smtp.gmail.com` |
| Port | `465` |
| Username | Gmail-Adresse (#1) |
| Password | App-Passwort (#2), **ohne Leerzeichen** |

Taucht ein Feld für den Mindestabstand zwischen Mails auf, den vorgeschlagenen Wert stehen lassen.

2. *Save*.
3. *Authentication* → *Rate Limits* → „Rate limit for sending emails“ auf **30** pro Stunde → *Save*.

✅ **Fertig, wenn** SMTP gespeichert ist, ohne Fehlermeldung.

**C5b. Mail-Vorlagen: Code statt Link**
Die Standard-Vorlagen enthalten nur einen Link, keinen Code – ohne diese Änderung kommt bei der Familie kein Code an.

1. *Authentication* → *Emails* → Reiter *Templates*. **Zwei** Vorlagen gleich ändern – **„Magic link or OTP“** und **„Confirm sign up“** (die zweite bekommt jede Person beim allerersten Login):
   - **Subject:** `Dein Code für Casa la Paz: {{ .Token }}`
   - **Body** (alles ersetzen):
     ```html
     <div style="font-family:-apple-system,Helvetica,Arial,sans-serif;color:#15232E">
       <h2 style="margin:0 0 12px">Casa la Paz</h2>
       <p>Dein Anmeldecode:</p>
       <p style="font-size:34px;font-weight:700;letter-spacing:6px;margin:8px 0 16px">{{ .Token }}</p>
       <p style="color:#5b6670">Gib ihn in der App ein. Er gilt eine Stunde.</p>
     </div>
     ```
   - jeweils *Save*

✅ **Fertig, wenn** beide Vorlagen `{{ .Token }}` im Betreff und im Text haben.
ℹ️ Der Code im Betreff sorgt dafür, dass das iPhone ihn schon in der Mitteilung zeigt und über der Tastatur zum Einfügen anbietet.

**C6. App-Adresse hinterlegen**
1. *Authentication* → *URL Configuration* → **Site URL**: `https://casalapaz.github.io` (bzw. mit deinem Organisationsnamen aus D1b – du kannst diesen Schritt auch nach D1b machen).

✅ **Fertig, wenn** die Site URL gespeichert ist.

**C7. Schlüssel notieren**
1. *Project Settings* (Zahnrad) → *API Keys* (bei manchen Projekten *Data API*):
   - **Project URL** → #4
   - **Publishable key** (`sb_publishable_…`) → #5
   - **Secret key** (`sb_secret_…`, ggf. *Reveal*) → #6
2. Falls dort nur alte Schlüssel stehen („anon“, „service_role“): anon = #5, service_role = #6. Funktioniert genauso.

✅ **Fertig, wenn** #4, #5 und #6 im Passwortmanager stehen.

---

## Teil D – GitHub: Konto, Organisation, Repo, Verbindung zu Claude (15 Min.)

**Warum zwei Ebenen:** GitHub erlaubt pro Person nur **ein** kostenloses Konto – deshalb dein privates Konto (Hotmail). Casa la Paz bekommt darunter eine kostenlose **Organisation**. Vorteile: die kürzeste mögliche Adresse (`https://casalapaz.github.io`) und eine saubere Übergabe, falls später jemand anderes die App betreut.

**D1. Privates Konto**
1. github.com → *Sign up* mit deiner **privaten Hotmail-Adresse**. Benutzername frei wählbar (taucht in der App-Adresse nicht auf).
2. Plan: **Free**. Nichts kaufen.

**D1b. Organisation anlegen**
1. Oben rechts Profilbild → *Your organizations* → *New organization* → **Free**.
2. Organization name: **`casalapaz`** (falls vergeben: `casalapaz-vinaros`). → Notizzettel **#7**
3. Contact email: die App-Gmail (#1). „This organization belongs to: **My personal account**“.
4. *Next* → Mitglieder hinzufügen überspringen → fertig.

✅ **Fertig, wenn** du unter *Your organizations* die neue Organisation siehst.

**D2. Repo anlegen**
1. Oben *+* → *New repository*.
2. **Owner: die Organisation** (nicht dein Benutzername!)
3. Repository name: **`<organisation>.github.io`** – also genau `casalapaz.github.io` (bzw. `casalapaz-vinaros.github.io`)
4. **Public**
5. *Add a README*: **aus** · .gitignore: *None* · License: *None*
6. *Create repository*.

✅ **Fertig, wenn** du eine leere Repo-Seite mit „Quick setup“ siehst. Die App-Adresse wird später **`https://<organisation>.github.io`** sein.

**D3. GitHub mit Claude verbinden**
1. claude.ai → *Einstellungen* → *Connectors* (bzw. *Integrationen*) → **GitHub** → *Verbinden*, mit deinem privaten Konto anmelden.
2. Wenn GitHub fragt, wo die App installiert werden soll: **die Organisation** wählen → **Only select repositories** → `<organisation>.github.io`.
3. **Wichtig:** Fragt GitHub nicht danach (z. B. weil dein Konto schon verbunden war), die Claude-App von Hand in der Organisation installieren: **github.com/apps/claude/installations/select_target** → `casalapaz` → *Only select repositories* → `casalapaz.github.io` → *Install*. Ohne diesen Schritt kann Claude das Repo lesen, aber nichts hochladen.

✅ **Fertig, wenn** GitHub in claude.ai als verbunden angezeigt wird.
*Alternative ohne Verbindung:* Im leeren Repo auf „uploading an existing file“ klicken und den **Inhalt** der ZIP-Datei hineinziehen (inkl. der Ordner `.github`, `icons`, `supabase`). Dann kann Claude künftige Versionen aber nicht selbst ausspielen.

---

## Teil E – Claude schaltet scharf (du schickst drei Werte)

Schick Claude in diesem Projekt eine Nachricht mit:
- **GitHub-Organisation** (#7)
- **Project URL** (#4)
- **Publishable key** (#5)

**Claude macht dann:**
1. trägt die drei Werte in die App ein (`LIVE`-Block in `index.html`)
2. lädt alles ins Repo hoch
3. sagt dir Bescheid, sobald du mit Teil F weitermachen kannst

✅ **Fertig, wenn** Claude meldet: „Code liegt im Repo“. *(Erledigt am 12.11., 19:05.)*

---

## Teil F – GitHub Pages und Wartungs-Jobs aktivieren (10 Min.)

**F1. Veröffentlichung prüfen** (bei Organisations-Seiten schaltet GitHub sie automatisch ein)
1. Im Repo *Settings* → links *Pages*: Dort steht „Your site is live at `https://casalapaz.github.io`“, Source *Deploy from a branch*, Branch `main`, `/ (root)`. Steht dort etwas anderes: genau so einstellen → *Save*.

✅ **Fertig, wenn** `https://casalapaz.github.io` den Anmeldebildschirm „Casa la Paz – Anmelden“ zeigt. *(Am 12.11. von Claude geprüft: online, Version 4.2.1, Datenbank erreichbar, unbekannte E-Mails werden abgewiesen.)*

**F2. Sicherungs-Passwort ausdenken**
Ein langes neues Passwort (z. B. vom Passwortmanager generiert) → #8. **Ohne dieses Passwort lassen sich die Sicherungen nicht öffnen.**

**F3. Geheimnisse für die Wartungs-Jobs**
1. Im Repo *Settings* → *Secrets and variables* → *Actions* → *New repository secret* – viermal:

| Name (exakt so) | Wert |
|---|---|
| `SUPABASE_URL` | #4 |
| `SUPABASE_PUBLISHABLE_KEY` | #5 |
| `SUPABASE_SECRET_KEY` | #6 |
| `BACKUP_PASSPHRASE` | #8 |

**F4. Jobs einmal von Hand starten**
1. Im Repo Reiter *Actions*. Falls gefragt: *I understand my workflows, go ahead and enable them*.
2. Links **„Supabase wach halten“** → *Run workflow* → *Run workflow*.
3. Links **„Wöchentliche Sicherung“** → *Run workflow* → *Run workflow*.
4. Ein bis zwei Minuten warten.

✅ **Fertig, wenn** beide Läufe einen **grünen Haken** haben und im Ordner `backups/` eine Datei `casa-la-paz-latest.json.gpg` liegt.
❌ **Rotes Kreuz?** Lauf anklicken, Screenshot an Claude.

---

## Teil I – Mitteilungen einrichten (10 Min., neu in 4.4.0, vor Teil G)

**Was es bringt:** Fragt jemand an, bekommen die Super-User, deren Freigabe fehlt, eine Mitteilung aufs iPhone – mit rotem Zähler am App-Symbol wie bei Mail (außerhalb der Hochsaison die beiden aus den anderen Familien, in der Hochsaison alle drei). In der App steht derselbe Zähler am Reiter *Anfragen*.

**Grenzen (von Apple vorgegeben):** nur iPhone mit **iOS 16.4 oder neuer**, nur in der App **vom Home-Bildschirm** (nicht in Safari), jede Person muss **einmal erlauben**. Der Zähler am Symbol aktualisiert sich bei jeder neuen Mitteilung und beim Öffnen der App – entscheidet z. B. Uli eine Anfrage, sieht Fanny die alte Zahl, bis sie die App öffnet (stille Hintergrund-Updates erlaubt Apple nicht).

**I1. Datenbank ergänzen**
1. Im Repo die Datei **`supabase/migrate-4.4.0-mitteilungen.sql`** öffnen → rechts oben *Copy raw file*.
2. Supabase → *SQL Editor* → *New query* → einfügen → *Run*. (Die Warnung „destructive operations“ ist bei diesem Skript unbedenklich.)

✅ **Fertig, wenn** „Success. No rows returned“ erscheint.

**I2. Zugangs-Token für GitHub anlegen** (damit GitHub die Server-Funktion für die Mitteilungen ausspielen darf)
1. **supabase.com/dashboard/account/tokens** öffnen – angemeldet mit dem **App-Konto** (Gmail #1), nicht mit einem privaten.
2. *Generate new token* → Name `GitHub Mitteilungen` → Ablauf: *Never* (falls gefragt) → *Generate token*.
3. Den Token (`sbp_…`) kopieren → Notizzettel **#10**. Er wird nur einmal angezeigt.

ℹ️ Der Token kann alles im Supabase-Konto der App – deshalb nur als GitHub-Secret ablegen, nirgends sonst. Weil das Konto nur Casa la Paz enthält, reicht sein Zugriff nicht weiter.

**I3. Token bei GitHub hinterlegen**
1. Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*.
2. Name: **`SUPABASE_ACCESS_TOKEN`**, Wert: #10 → *Add secret*.

**I4. Mitteilungen ausspielen**
1. Repo → Reiter *Actions* → links **„Mitteilungen ausspielen“** → *Run workflow* → *Run workflow* (die 404-Seite danach ist der bekannte Anzeigefehler, der Lauf startet trotzdem).
2. 1–2 Minuten warten.

✅ **Fertig, wenn** der Lauf einen **grünen Haken** hat. Beim ersten Lauf entstehen dabei die Schlüssel für die Mitteilungen; sie werden direkt in Supabase gespeichert und tauchen nirgends sonst auf.
❌ **Rot?** Lauf anklicken, Screenshot an Claude.

**I5. Einschalten – je einmal bei Micha, Uli und Fanny**
1. App **über das Symbol auf dem Home-Bildschirm** öffnen.
2. Reiter *Anfragen* → Karte „Neue Anfragen sofort sehen“ → **Einschalten** → iPhone fragt → **Erlauben**. (Alternativ: Avatar oben rechts → *Konto* → *Mitteilungen einschalten*.)

✅ **Fertig, wenn** im *Konto* bei *Mitteilungen* „An“ steht.
ℹ️ Sub-User sehen den Schalter nicht – sie bekommen keine Mitteilungen.

---

## Teil G – Testlauf mit zwei Personen (15 Min.)

Bevor die Familie loslegt, einmal den ganzen Ablauf prüfen – du als Sub-User, Micha als Super-User.

**G1. Du (iPhone)**
1. App-Adresse in **Safari** öffnen → Teilen-Symbol → **Zum Home-Bildschirm** → *Hinzufügen*.
2. **Die App über das neue Symbol öffnen** (nicht in Safari weitermachen).
3. E-Mail eingeben → *Code senden* → Code aus der Mail eintippen.
4. Im Kalender einen **Test-Aufenthalt außerhalb der Hochsaison** anlegen (z. B. im Oktober 2027, 2 Nächte).

✅ Toast „Reserviert. Uli oder Fanny gibt frei.“, Balken schraffiert im Kalender.

5. Zweiter Test **in der Hochsaison** (z. B. 2 Nächte im Juli 2027).

✅ Beim Planen erscheint der orange **Hochsaison-Hinweis**; Toast „Micha, Uli und Fanny geben frei“.
✅ Hat Micha Teil I5 erledigt: Auf seinem iPhone erscheint wenige Sekunden später „Neue Anfrage von Leon“, das App-Symbol zeigt eine rote **1** (beim ersten Test außerhalb der Hochsaison bekommt Micha keine – da geben Uli oder Fanny frei).

**G2. Micha (sein iPhone oder du loggst dich auf einem zweiten Gerät mit seiner Adresse ein)**
1. Anmelden wie in G1.
2. Tab *Anfragen*: Die Hochsaison-Anfrage steht unter „Wartet auf dich“ mit „0 von 3 Freigaben“ → *Freigeben*.

✅ Toast „Deine Freigabe zählt. Es fehlen noch Uli und Fanny.“
ℹ️ Die Oktober-Anfrage sieht Micha unter „Wartet auf andere“ – richtig so, außerhalb der Hochsaison gibt nur eine andere Familie frei.

**G3. Aufräumen**
1. In deiner App beide Test-Aufenthalte öffnen → *Stornieren* → *Wirklich stornieren?*

✅ **Fertig, wenn** der Kalender wieder ohne Testbuchungen ist.

---

## Teil H – Familie aufs iPhone bringen (10 Min. pro Person)

**H1. Bestehende Buchungen übernehmen** (vor dem Rollout)
1. Aus kalender.digital alle **Buchungen ab heute** als Liste (Wer, Anreise, Abreise, bestätigt/offen) an Claude schicken – Screenshot reicht.
2. Claude baut daraus eine SQL-Datei → du fügst sie wie in C2 im SQL Editor ein → *Run*.

✅ Der Kalender in der App zeigt dieselben Aufenthalte wie kalender.digital.

**H2. Nachricht an die Familie** (Vorlage – per WhatsApp verschicken, `<Adresse>` ersetzen)

> Hallo zusammen, unser Belegungsplan für Vinaròs zieht um: **<Adresse>**
> 1. Link in **Safari** öffnen (nicht in WhatsApp)
> 2. Teilen-Symbol → „Zum Home-Bildschirm“
> 3. App über das neue Symbol öffnen, eigene E-Mail eingeben, Code aus der Mail eintippen – fertig, ihr bleibt angemeldet.
> Ab sofort bitte nur noch hier eintragen. Fragen → Leon.

**H3. Eltern persönlich einrichten**
Bei Micha (und ggf. deiner Mutter) einmal zusammen am iPhone die Schritte aus G1 durchgehen. Danach bleibt die Anmeldung bestehen.

**H4. kalender.digital abschalten**
Erst wenn alle drei Familien in der App sind: in kalender.digital einen Hinweis auf die neue App eintragen und – falls kalender.digital das anbietet – Bearbeiten für andere sperren, damit niemand doppelt bucht.

✅ **Fertig, wenn** jede Person einmal angemeldet war. Prüfen: In Supabase *Authentication* → *Users* steht für jede Person ein Eintrag.

---

## Was danach automatisch läuft

| Was | Wann | Wozu |
|---|---|---|
| Wach-halten-Aufruf | täglich, 07:17 Uhr (Sommerzeit 08:17) | Kostenlose Supabase-Projekte schlafen sonst nach 7 Tagen ohne Nutzung ein. |
| Verschlüsselte Sicherung | sonntags, 04:41 Uhr (Sommerzeit 05:41) | Alle Personen und Buchungen in `backups/`, die letzten 12 Wochen. |
| App-Updates | beim Öffnen | Die App prüft `version.json` und lädt neue Versionen selbst. Niemand muss etwas tun. |
| Mitteilungen | bei jeder neuen Anfrage | Die App stößt die Server-Funktion `push` an; die Datenbank bestimmt, wer benachrichtigt wird (jede Anfrage höchstens einmal pro Person). |
| Server-Funktion neu ausspielen | wenn sich `supabase/functions/` ändert | Workflow „Mitteilungen ausspielen“ läuft dann von selbst. |

**Kosten im Blick:** alles 0 €. Grenzen, die für Casa la Paz nie erreicht werden: GitHub Pages 1 GB / 100 GB Datenverkehr pro Monat (die App hat 120 KB); Supabase 500 MB Datenbank, 50.000 aktive Nutzer pro Monat. Einzige echte Grenze: **2 aktive kostenlose Supabase-Projekte pro Konto** – relevant erst bei weiteren Apps mit eigener Datenbank.

**Neue Version ausspielen:** macht Claude (Repo ist verbunden). Werkbank mit Testdaten bleibt das Claude-Artifact „Casa la Paz“.

---

## Problemlösung

| # | Problem | Lösung |
|---|---|---|
| P1 | „Diese E-Mail-Adresse ist nicht freigeschaltet“ | Adresse in `people` fehlt oder ist anders geschrieben (Groß-/Kleinschreibung, Leerzeichen, Tippfehler). |
| P2 | Kein Code kommt an | Spam-Ordner prüfen. Dann SMTP-Daten (C5) prüfen. Supabase *Logs* → *Auth* zeigt den Fehler. Häufigste Ursache: App-Passwort mit Leerzeichen eingetragen. |
| P3 | C2 meldet einen Fehler bei `auth.users` | Den Block „Anmelden dürfen nur E-Mail-Adressen aus people“ aus `setup.sql` entfernen und erneut *Run*. Dann *Authentication* → *Sign In / Providers* → „Allow new users to sign up“ **aus**, und jede Person unter *Authentication* → *Users* → *Add user* → *Create new user* einmal mit ihrer E-Mail anlegen („Auto Confirm User“ an). |
| P4 | „Der Code stimmt nicht oder ist abgelaufen“ | Neuen Code anfordern (nach 60 Sekunden möglich). Immer den **neuesten** Code nehmen. |
| P5 | In Safari angemeldet, aber die App will wieder einen Code | Normal: Safari und Home-Bildschirm-App teilen keine Anmeldung. Einmal in der App anmelden. |
| P6 | App zeigt „Keine Verbindung“ | Internet prüfen. Hält es an: Supabase-Dashboard öffnen – ist das Projekt pausiert, *Restore project*, und prüfen, warum „Supabase wach halten“ rot ist. |
| P7 | Wartungs-Job rot | Meist ein Tippfehler im Secret-Namen (F3). Namen exakt wie in der Tabelle. |
| P8 | Sicherung öffnen | Datei aus `backups/` herunterladen, am Mac im Terminal: `gpg --decrypt casa-la-paz-latest.json.gpg > sicherung.json`, Passwort #8. Oder Claude die Datei geben und das Passwort selbst eintippen. |
| P10 | „Supabase wach halten“ läuft nicht mehr (Reiter *Actions*: Workflow grau/„disabled“) | GitHub schaltet geplante Jobs in öffentlichen Repos nach **60 Tagen ohne Änderung am Repo** ab. Die sonntägliche Sicherung legt jede Woche eine neue Datei ab und hält das Repo damit aktiv – solange sie grün läuft. Wenn doch: Workflow anklicken → *Enable workflow*, dann prüfen, warum die Sicherung rot ist. |
| P11 | Mitteilung kommt nicht an | 1. iPhone: *Einstellungen* → *Mitteilungen* → *Casa la Paz* → Mitteilungen erlauben und **Kennzeichen** an; Fokus/„Nicht stören“ prüfen. 2. In der App *Konto* → Mitteilungen: steht dort „An“? 3. Supabase → *Edge Functions* → `push` → *Logs*: Zeilen „push an … fehlgeschlagen“ an Claude schicken. Eine Mitteilung kommt pro Anfrage nur einmal; alte Anfragen von vor dem Einschalten zählt nur der rote Zähler. |
| P12 | Workflow „Mitteilungen ausspielen“ gelb/„übersprungen“ | Secret `SUPABASE_ACCESS_TOKEN` fehlt oder ist falsch benannt (I3). Danach *Run workflow*. |
| P9 | Person hinzufügen | *Table Editor* → `people` → *Insert row*: `id` (kurz, klein, z. B. `lena`), `name`, `stamm` (`micha`/`uli`/`fanny`), `is_super` = false, `email`, `sort`. |

---

## Abschluss-Checkliste

- [x] Teil 0: vier Entscheidungen getroffen und eingebaut
- [ ] B: Gmail-Konto + App-Passwort + Weiterleitung an Hotmail
- [ ] C: Supabase-Projekt, SQL ausgeführt, E-Mails eingetragen (mind. Leon + Micha), Login-Einstellungen, SMTP, Code-Vorlagen, Rate Limit, Schlüssel notiert
- [ ] D: privates GitHub-Konto, Organisation, Repo `<organisation>.github.io` (public), mit Claude verbunden
- [ ] E: drei Werte an Claude, Code liegt im Repo
- [ ] F: Pages live, 4 Secrets, beide Jobs grün
- [ ] I: Mitteilungen – SQL, Token, Workflow grün, bei Micha/Uli/Fanny eingeschaltet
- [ ] G: Testlauf Leon + Micha ok (inkl. Mitteilung), Testbuchungen storniert
- [ ] H: Bestandsbuchungen importiert, Familie eingeladen, Eltern eingerichtet, kalender.digital stillgelegt
