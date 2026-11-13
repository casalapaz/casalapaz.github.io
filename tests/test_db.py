import json, sys
import psycopg

DSN = "host=/tmp/pg port=5433 user=postgres dbname=t1"
conn = psycopg.connect(DSN, autocommit=True)
ok = fail = 0

def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1; print("  ok  ", name)
    else: fail += 1; print("  FAIL", name, info)

def as_user(email, sql, params=()):
    """Run sql as role authenticated with a JWT carrying email. Returns (rows, error)."""
    with conn.cursor() as c:
        try:
            c.execute("begin")
            c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email, "role": "authenticated"}),))
            c.execute("set local role authenticated")
            c.execute(sql, params)
            rows = c.fetchall() if c.description else []
            c.execute("commit")
            return rows, None
        except Exception as e:
            c.execute("rollback")
            return None, str(e).split("\n")[0]

def as_role(role, sql):
    with conn.cursor() as c:
        try:
            c.execute("begin"); c.execute(f"set local role {role}"); c.execute(sql)
            rows = c.fetchall() if c.description else []
            c.execute("commit"); return rows, None
        except Exception as e:
            c.execute("rollback"); return None, str(e).split("\n")[0]

def admin(sql, params=()):
    with conn.cursor() as c:
        c.execute(sql, params)
        return c.fetchall() if c.description else []

admin("delete from bookings")
for pid in ["micha", "leon", "uli", "fanny", "karlina", "kaspar", "marilen"]:
    admin("update people set email = %s where id = %s", (f"{pid}@x.de", pid))

def create(who, a, d, comp="{}", guests=0, note=""):
    return as_user(f"{who}@x.de", "select id, status, stamm from create_booking(%s, %s, %s, %s, %s)", (a, d, comp, guests, note))

def decide(who, bid, verdict, reason=""):
    return as_user(f"{who}@x.de", "select status from decide_booking(%s, %s, %s)", (bid, verdict, reason))

print("Zugriff")
r, e = as_role("anon", "select * from bookings")
check("anon kann Buchungen nicht lesen", e and "permission denied" in e, e)
r, e = as_user("fremd@y.de", "select count(*) from bookings")
check("Fremde E-Mail sieht nichts", r == [(0,)], (r, e))
r, e = create("fremd", "2027-07-01", "2027-07-05")
check("Fremde E-Mail kann nicht buchen", e and "nicht angemeldet" in e, e)
r, e = as_user("leon@x.de", "select email from people")
check("E-Mails sind nicht lesbar", e and "permission denied" in e, e)
r, e = as_user("leon@x.de", "select id, name from people order by sort")
check("Namen sind lesbar (13 inkl. Martina, Svantje, Kay)", r and len(r) == 13, (r, e))
r, e = as_user("leon@x.de", "insert into bookings (stamm, booked_by, arrive, depart, status) values ('micha','leon','2027-01-01','2027-01-02','confirmed')")
check("Direktes Schreiben gesperrt", e and "permission denied" in e, e)
r, e = as_user("leon@x.de", "select whoami()")
check("whoami liefert leon", r == [("leon",)], (r, e))
r, e = as_user("LEON@X.DE", "select whoami()")
check("E-Mail-Großschreibung egal", r == [("leon",)], (r, e))
r, e = as_user("leon@x.de", "select expire_pending()")
check("expire_pending nicht direkt aufrufbar", e and "permission denied" in e, e)

print("Buchen")
r, e = create("micha", "2027-05-01", "2027-05-14", "{}")
check("Super-User bucht bestätigt", r and r[0][1] == "confirmed", (r, e)); m1 = r[0][0]
r, e = create("leon", "2027-05-08", "2027-05-21", "{}", 2, "Mit Freunden")
check("Sub-User reserviert pending (gleicher Stamm darf überlappen)", r and r[0][1] == "pending", (r, e)); l1 = r[0][0]
r, e = create("uli", "2027-05-10", "2027-05-12")
check("Fremder Stamm überlappt -> Fehler", e and "Überschneidet sich" in e, e)
r, e = create("uli", "2027-05-20", "2027-05-22")
check("Überlappung mit offener Anfrage ebenfalls gesperrt", e and "Überschneidet sich" in e, e)
r, e = create("uli", "2027-05-21", "2027-05-28")
check("Wechseltag erlaubt", r and r[0][1] == "confirmed", (r, e)); u1 = r[0][0]
r, e = create("leon", "2026-11-01", "2026-11-20")
check("Anreise in der Vergangenheit -> Fehler", e and "Vergangenheit" in e, e)
r, e = create("leon", "2027-03-05", "2027-03-05")
check("Abreise = Anreise -> Fehler", e and "Abreise muss nach" in e, e)
r, e = create("leon", "2027-03-01", "2027-03-05", "{kaspar}")
check("Mitreisende aus anderem Stamm -> Fehler", e and "deiner Familie" in e, e)
r, e = create("leon", "2027-03-01", "2027-03-05", "{leon,marilen,marilen}")
check("Mitreisende bereinigt", r is not None, e)
cmp = admin("select companions from bookings where id = %s", (r[0][0],))
check("…ohne sich selbst und ohne Doppelte", cmp == [(["marilen"],)], cmp)
r, e = create("leon", "2027-02-01", "2027-03-05")
check("Mehr als 31 Nächte -> Fehler", e and "31 Nächte" in e, e)
r, e = create("leon", "2027-02-01", "2027-03-04")
check("Genau 31 Nächte erlaubt", r is not None, e)
r, e = create("leon", "2027-03-10", "2027-03-12", "{}", 13)
check("Mehr als 12 Gäste -> Fehler", e is not None, e)

print("Entscheiden")
r, e = decide("micha", l1, "approve")
check("Eigener Stamm kann nicht freigeben", e and "anderen Familie" in e, e)
r, e = decide("kaspar", l1, "reject", "Nein danke")
check("Sub-User kann nicht ablehnen", e and "Super-User" in e, e)
r, e = decide("fanny", l1, "reject", "  ")
check("Ablehnen ohne Begründung -> Fehler", e and "Begründung" in e, e)
r, e = decide("fanny", l1, "approve")
check("Anderer Stamm gibt frei", r == [("confirmed",)], (r, e))
r, e = decide("uli", l1, "reject", "Zu spät")
check("Erste Entscheidung gilt", e and "schon entschieden" in e, e)
d = admin("select decided_by from bookings where id = %s", (l1,))
check("decided_by = fanny", d == [("fanny",)], d)

print("Verfall")
r, e = create("karlina", "2027-10-20", "2027-10-22"); kx = r[0][0]
admin("update bookings set created_at = now() - interval '20 days' where id = %s", (kx,))
create("fanny", "2027-12-01", "2027-12-02")
st = admin("select status from bookings where id = %s", (kx,))
check("Nach 20 Tagen noch offen (Frist 21 Tage)", st == [("pending",)], st)
r, e = create("karlina", "2027-09-04", "2027-09-12")
k1 = r[0][0]
admin("update bookings set created_at = now() - interval '22 days' where id = %s", (k1,))
r, e = create("fanny", "2027-09-05", "2027-09-08")
check("Abgelaufene Anfrage blockiert nicht mehr", r and r[0][1] == "confirmed", (r, e))
st = admin("select status from bookings where id = %s", (k1,))
check("…und steht auf expired", st == [("expired",)], st)
r, e = create("kaspar", "2027-10-01", "2027-10-05"); k2 = r[0][0]
admin("update bookings set created_at = now() - interval '22 days' where id = %s", (k2,))
r, e = decide("micha", k2, "approve")
check("Abgelaufene Anfrage nicht mehr freigebbar", e and "verfallen" in e, e)

print("Stornieren")
r, e = as_user("kaspar@x.de", "select status from cancel_booking(%s)", (m1,))
check("Fremder kann nicht stornieren", e and "nicht möglich" in e, e)
r, e = as_user("leon@x.de", "select status from cancel_booking(%s)", (m1,))
check("Sub-User kann Buchung des Super-Users nicht stornieren", e and "nicht möglich" in e, e)
r, e = as_user("micha@x.de", "select status from cancel_booking(%s)", (l1,))
check("Super-User storniert im eigenen Stamm", r == [("cancelled",)], (r, e))
r, e = as_user("micha@x.de", "select status from cancel_booking(%s)", (l1,))
check("Doppelt stornieren -> Fehler", e is not None, e)
r, e = create("uli", "2027-05-14", "2027-05-21")
check("Stornierter Zeitraum ist wieder frei", r and r[0][1] == "confirmed", (r, e))

print("Hochsaison")
import subprocess, re as _re
def hs(a, d):
    r = admin("select touches_high_season(%s, %s)", (a, d)); return r[0][0]
check("Abreise am ersten Hochsaison-Tag zählt nicht", hs("2027-06-20", "2027-06-28") is False)
check("Eine Nacht in der Hochsaison zählt", hs("2027-06-20", "2027-06-29") is True)
check("Letzter Ferientag NRW 2026 (1.9.) zählt", hs("2026-09-01", "2026-09-03") is True)
check("Ab 2.9.2026 keine Hochsaison", hs("2026-09-02", "2026-09-05") is False)
check("Hochsaison 2028 = Juli/August", hs("2028-06-28", "2028-07-01") is False and hs("2028-06-28", "2028-07-02") is True)
check("Jahreswechsel-Aufenthalt im Winter", hs("2026-12-28", "2027-01-04") is False)
# App und Datenbank müssen dieselbe Hochsaison haben
html = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "index.html"), encoding="utf-8").read()
logic = html[html.index("/* ===================== LOGIC START"):html.index("/* ===================== LOGIC END")]
js = logic + "\nconsole.log(JSON.stringify([2026, 2027, 2028].map(highSeason)));"
out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True).stdout)
db_ranges = [admin("select lower(r)::text, (upper(r) - 1)::text from high_season_range(%s) r", (y,))[0] for y in (2026, 2027, 2028)]
check("App und Datenbank: gleiche Hochsaison 2026–2028", [(o["from"], o["to"]) for o in out] == db_ranges, (out, db_ranges))

r, e = create("leon", "2027-07-17", "2027-07-25"); h1 = r[0][0]
st = admin("select status, high_season from bookings where id = %s", (h1,))
check("Sub-User in der Hochsaison: pending + markiert", st == [("pending", True)], st)
r, e = decide("micha", h1, "approve")
check("Eigene Familie darf in der Hochsaison freigeben", r == [("pending",)], (r, e))
r, e = decide("micha", h1, "approve")
check("Doppelt freigeben -> Fehler", e and "schon freigegeben" in e, e)
r, e = decide("micha", h1, "reject", "Doch nicht")
check("Nach eigener Freigabe nicht mehr ablehnen", e and "schon freigegeben" in e, e)
r, e = decide("kaspar", h1, "approve")
check("Sub-User kann nicht freigeben", e and "Super-User" in e, e)
r, e = decide("fanny", h1, "approve")
check("Zweite Freigabe: weiter pending", r == [("pending",)], (r, e))
r, e = decide("uli", h1, "approve")
check("Dritte Freigabe: bestätigt", r == [("confirmed",)], (r, e))
a = admin("select jsonb_array_length(approvals), decided_by from bookings where id = %s", (h1,))
check("Drei Freigaben gespeichert, decided_by = letzter", a == [(3, "uli")], a)
r, e = create("kaspar", "2027-08-20", "2027-08-25"); h2 = r[0][0]
decide("uli", h2, "approve")
r, e = decide("fanny", h2, "reject", "Da kommt der Dachdecker")
check("Ein Nein reicht auch nach Teil-Freigabe", r == [("rejected",)], (r, e))
r, e = create("fanny", "2027-08-26", "2027-08-30")
check("Super-User bucht in der Hochsaison direkt", r and r[0][1] == "confirmed", (r, e))
r, e = create("marilen", "2027-11-10", "2027-11-14"); h3 = r[0][0]
r, e = decide("micha", h3, "approve")
check("Außerhalb der Hochsaison: eigene Familie weiter gesperrt", e and "anderen Familie" in e, e)
r, e = decide("uli", h3, "approve")
check("Außerhalb: eine Freigabe reicht", r == [("confirmed",)], (r, e))

print("Datenbank-Absicherung (falls jemand an den Funktionen vorbei schreibt)")
try:
    admin("insert into bookings (stamm, booked_by, arrive, depart, status) values ('fanny','fanny','2027-05-05','2027-05-06','pending')")
    check("Ausschlussbedingung greift", False)
except Exception as ex:
    check("Ausschlussbedingung greift", "one_stamm_at_a_time" in str(ex), str(ex)[:80])
try:
    admin("insert into bookings (stamm, booked_by, arrive, depart, status) values ('fanny','fanny','2027-12-05','2027-12-06','rejected')")
    check("Ablehnung ohne Begründung unmöglich", False)
except Exception as ex:
    check("Ablehnung ohne Begründung unmöglich", "check" in str(ex).lower(), str(ex)[:80])
try:
    admin("update people set is_super = true where id = 'leon'")
    check("Nur ein Super-User pro Stamm", False)
except Exception as ex:
    check("Nur ein Super-User pro Stamm", "people_one_super_per_stamm" in str(ex), str(ex)[:80])

print("Anmeldung")
try:
    admin("insert into auth.users (email) values ('fremd@y.de')")
    check("Unbekannte E-Mail kann sich nicht registrieren", False)
except Exception as ex:
    check("Unbekannte E-Mail kann sich nicht registrieren", "nicht freigeschaltet" in str(ex), str(ex)[:80])
admin("insert into auth.users (email) values ('Leon@X.de')")
check("Bekannte E-Mail kann sich registrieren", True)
r, e = as_role("anon", "select ping()")
check("ping für Keepalive", r is not None, e)

print("Mitreisende ohne Login")
admin("delete from bookings")
r, e = create("micha", "2028-03-01", "2028-03-05", "{martina,leon}")
check("Micha bucht mit Martina", r and r[0][1] == "confirmed", e)
r2, _ = as_user("leon@x.de", "select companions from bookings")
check("Martina steht als Mitreisende drin", r2 and "martina" in r2[0][0], r2)
r, e = create("leon", "2028-04-01", "2028-04-05", "{kay}")
check("Kay nicht in Michas Familie mitnehmbar", e and "Familie" in e, e)
r, e = create("uli", "2028-04-01", "2028-04-05", "{svantje,kajus}")
check("Uli bucht mit Svantje", r and r[0][1] == "confirmed", e)
r, e = as_user("martina@x.de", "select count(*) from bookings")
check("Martina ohne E-Mail kann nichts lesen", r == [(0,)], (r, e))
admin("delete from bookings")

print("Mitteilungen")
admin("delete from bookings"); admin("delete from push_subscriptions")
EP = "https://web.push.apple.com/QF"
KEYS = ("B" + "x" * 86, "a" * 22)
def sub(who, ep):
    return as_user(f"{who}@x.de", "select save_push_subscription(%s, %s, %s)", (ep, *KEYS))
def due(kind="request"):
    r, e = as_role("service_role", f"select person_id, endpoint, booked_by, high_season, open_count, booking_id::text, approvers, decided_by, reason from push_due() where kind = '{kind}'")
    assert e is None, e
    return r
r, e = as_role("anon", "select save_push_subscription('https://x', 'y', 'z')")
check("anon kann kein Gerät anmelden", e and "permission denied" in e, e)
r, e = as_user("leon@x.de", "select * from push_subscriptions")
check("Geräte-Liste für Nutzer nicht lesbar", e and "permission denied" in e, e)
r, e = as_user("leon@x.de", "select * from push_due()")
check("push_due nur für den Server", e and "permission denied" in e, e)
r, e = as_user("leon@x.de", "select push_report('[]', '{}', '{}')")
check("push_report nur für den Server", e and "permission denied" in e, e)
r, e = as_user("fremd@y.de", "select save_push_subscription(%s, %s, %s)", (EP + "0", *KEYS))
check("Fremde E-Mail kann kein Gerät anmelden", e and "nicht angemeldet" in e, e)
r, e = sub("uli", "http://unsicher")
check("Nur https-Adressen", e and "check" in e.lower(), e)
# Bestehende offene Anfrage vor dem Einschalten -> keine Flut
r, e = create("karlina", "2027-10-01", "2027-10-04"); old = r[0][0]
r, e = sub("micha", EP + "m1"); check("Micha meldet Gerät an", e is None, e)
sub("micha", EP + "m2"); sub("uli", EP + "u1"); sub("fanny", EP + "f1"); sub("leon", EP + "l1")
check("Alte Anfrage gilt beim Einschalten als gemeldet", [x for x in due() if x[5] == str(old)] == [], due())
n = admin("select count(*) from push_subscriptions")[0][0]
check("Gerät erneut anmelden legt nichts doppelt an", (sub("micha", EP + "m1")[1] is None) and admin("select count(*) from push_subscriptions")[0][0] == n)
# Neue Anfrage außerhalb der Hochsaison (Leon, Michas Familie) -> Uli + Fanny
r, e = create("leon", "2027-10-20", "2027-10-24"); b1 = r[0][0]
d = due()
check("Neue Anfrage: Uli und Fanny bekommen sie, nicht Micha/Leon", sorted({x[0] for x in d}) == ["fanny", "uli"], d)
check("Name und Hochsaison im Ergebnis", all(x[2] == "Leon" and x[3] is False for x in d), d)
check("Zähler = offene Anfragen der Person (Uli: Karlina zählt nicht, eigene Familie)", {x[0]: x[4] for x in d} == {"uli": 1, "fanny": 2}, d)
as_role("service_role", "select push_report('[{\"booking_id\": \"%s\", \"person_id\": \"uli\"}]', '{%s}', '{%s}')" % (b1, EP + "f1", EP + "u1"))
d = due()
check("Nach Versand an Uli: nichts mehr offen für Uli", not [x for x in d if x[0] == "uli"], d)
check("Abgemeldetes Gerät (410) wird gelöscht", admin("select count(*) from push_subscriptions where endpoint = %s", (EP + "f1",))[0][0] == 0)
check("Ohne Gerät: Fanny erscheint nicht", not [x for x in d if x[0] == "fanny"], d)
check("last_ok wird gesetzt", admin("select last_ok is not null from push_subscriptions where endpoint = %s", (EP + "u1",)) == [(True,)])
sub("fanny", EP + "f2")
check("Neues Gerät: offene Anfragen gelten als gemeldet", not [x for x in due() if x[0] == "fanny"], due())
# Hochsaison: alle drei inkl. eigener Familie
r, e = create("leon", "2027-07-20", "2027-07-24"); b2 = r[0][0]
d = [x for x in due() if x[5] == str(b2)]
check("Hochsaison: Micha (beide Geräte), Uli, Fanny", sorted(x[0] for x in d) == ["fanny", "micha", "micha", "uli"] and all(x[3] for x in d), d)
decide("uli", b2, "approve")
d = [x for x in due() if x[5] == str(b2)]
check("Wer schon freigegeben hat, bekommt nichts mehr", sorted(x[0] for x in d) == ["fanny", "micha", "micha"], d)
decide("fanny", b2, "reject", "Da ist schon was los")
check("Abgelehnt: keine Mitteilung mehr fällig", not [x for x in due() if x[5] == str(b2)], due())
# Verfall
admin("update bookings set created_at = now() - interval '22 days' where id = %s", (b1,))
check("Verfallene Anfrage: keine Mitteilung, Zähler sinkt", not [x for x in due() if x[5] == str(b1)] and admin("select status from bookings where id = %s", (b1,)) == [("expired",)])
# Abmelden
r, e = as_user("uli@x.de", "select delete_push_subscription(%s)", (EP + "m1",))
check("Fremdes Gerät kann nicht abgemeldet werden", admin("select count(*) from push_subscriptions where endpoint = %s", (EP + "m1",))[0][0] == 1)
as_user("micha@x.de", "select delete_push_subscription(%s)", (EP + "m1",))
check("Eigenes Gerät abmelden", admin("select count(*) from push_subscriptions where endpoint = %s", (EP + "m1",))[0][0] == 0)
for i in range(7): sub("leon", EP + f"l{i+2}")
check("Höchstens 5 Geräte pro Person", admin("select count(*) from push_subscriptions where person_id = 'leon'")[0][0] == 5)
src = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "supabase", "migrate-4.5.0-mitteilungen.sql"), encoding="utf-8").read().strip()
setup_src = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "supabase", "setup.sql"), encoding="utf-8").read()
check("Migration 4.5.0 steht wortgleich in setup.sql", src in setup_src)
src46 = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "supabase", "migrate-4.6.0-echtzeit.sql"), encoding="utf-8").read().strip()
check("Migration 4.6.0 steht wortgleich in setup.sql", src46 in setup_src)
check("Buchungen sind für Realtime freigegeben", admin("select count(*) from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'bookings'") == [(1,)])

print("Mitteilungen über Entscheidungen (an die anfragende Person)")
admin("delete from bookings"); admin("delete from push_subscriptions"); admin("delete from push_decided")
for w in ("leon", "karlina", "micha", "uli", "fanny"): sub(w, EP + "d-" + w)
r, e = create("leon", "2027-07-05", "2027-07-09"); hs = r[0][0]
decide("micha", hs, "approve")
check("Hochsaison, 1 von 3: keine Mitteilung an Leon", due("confirmed") == [], due("confirmed"))
decide("fanny", hs, "approve")
check("Hochsaison, 2 von 3: weiterhin keine", due("confirmed") == [], due("confirmed"))
decide("uli", hs, "approve")
d = due("confirmed")
check("3 von 3: Leon bekommt 'freigegeben'", [(x[0], x[5]) for x in d] == [("leon", str(hs))], d)
check("…mit allen Freigebenden in Reihenfolge", d and d[0][6] == ["Micha", "Fanny", "Uli"], d)
check("Super-User bekommen keine Entscheidungs-Mitteilung", not [x for x in due("confirmed") + due("rejected") if x[0] != "leon"])
r, e = create("karlina", "2027-10-11", "2027-10-14"); n1 = r[0][0]
decide("micha", n1, "approve")
d = [x for x in due("confirmed") if x[5] == str(n1)]
check("Außerhalb der Hochsaison: eine Freigabe reicht, Karlina erfährt 'Micha'", [(x[0], x[6]) for x in d] == [("karlina", ["Micha"])], d)
r, e = create("leon", "2027-11-11", "2027-11-14"); rj = r[0][0]
decide("fanny", rj, "reject", "Da wird das Dach gemacht")
d = due("rejected")
check("Abgelehnt: Leon bekommt Name und Begründung", [(x[0], x[7], x[8]) for x in d] == [("leon", "Fanny", "Da wird das Dach gemacht")], d)
r, e = create("fanny", "2027-12-01", "2027-12-05")
check("Super-User-Buchung (sofort bestätigt): keine Mitteilung", not [x for x in due("confirmed") if x[0] == "fanny"])
r, e = create("marilen", "2027-12-10", "2027-12-12"); cn = r[0][0]
as_user("marilen@x.de", "select cancel_booking(%s)", (cn,))
check("Storno: keine Entscheidungs-Mitteilung", not [x for x in due("confirmed") + due("rejected") if x[5] == str(cn)])
as_role("service_role", "select push_report('[{\"kind\": \"confirmed\", \"booking_id\": \"%s\", \"person_id\": \"leon\"}]', '{}', '{}')" % hs)
check("Nach Versand nicht doppelt", not [x for x in due("confirmed") if x[5] == str(hs)])
check("…und die Anfrage-Mitteilungen bleiben unberührt", admin("select count(*) from push_sent where booking_id = %s", (hs,)) == [(0,)])
admin("update bookings set decided_at = now() - interval '4 days' where id = %s", (n1,))
check("Älter als 3 Tage: wird nicht mehr nachgeliefert", not [x for x in due("confirmed") if x[5] == str(n1)])
admin("update bookings set decided_at = now() where id = %s", (n1,))
admin("delete from push_subscriptions where person_id = 'karlina'"); sub("karlina", EP + "d-karlina2")
check("Neues Gerät: schon entschiedene eigene Anfragen gelten als gemeldet", not [x for x in due("confirmed") if x[5] == str(n1)])
admin("delete from bookings"); admin("delete from push_subscriptions")

print(f"\n{ok} ok, {fail} fehlgeschlagen")
sys.exit(1 if fail else 0)
