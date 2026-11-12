"""End-to-end: echte index.html im Browser, Supabase-Aufrufe gehen an das lokale Postgres
(gleiche SQL-Regeln wie in Supabase). Prüft Anmeldung, Laden, Buchen, Freigeben, Konflikt, Abmelden, Demo-Modus."""
import asyncio, json, os, sys, time, threading, http.server, functools, re
from urllib.parse import urlparse, parse_qs
import psycopg
from playwright.async_api import async_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHOTS = os.environ.get("SHOTS", "/tmp/shots")
SB = re.search(r'url: "(https://[^"]+)"', open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()).group(1)   # Supabase-Adresse aus LIVE
conn = psycopg.connect("host=/tmp/pg port=5433 user=postgres dbname=t1", autocommit=True)
ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1; print("  ok  ", name)
    else: fail += 1; print("  FAIL", name, info)

def admin(sql, params=()):
    with conn.cursor() as c:
        c.execute(sql, params); return c.fetchall() if c.description else []

def as_user(email, sql, params=()):
    with conn.cursor() as c:
        try:
            c.execute("begin")
            c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}),))
            c.execute("set local role authenticated")
            c.execute(sql, params); r = c.fetchall()
            c.execute("commit"); return r, None
        except Exception as e:
            c.execute("rollback"); return None, getattr(e, "diag", None) and e.diag.message_primary or str(e)

# ---------- Testdaten ----------
admin("delete from bookings")
admin("delete from auth.users")
for pid in ["micha", "leon", "uli", "fanny", "karlina", "kaspar", "marilen"]:
    admin("update people set email = %s where id = %s", (f"{pid}@x.de", pid))
admin("""insert into bookings (stamm, booked_by, companions, arrive, depart, status, decided_at) values
  ('micha','micha','{}','2027-03-20','2027-03-28','confirmed', now()),
  ('fanny','fanny','{}','2027-06-28','2027-07-12','confirmed', now()),
  ('uli','uli','{kaspar}','2027-07-31','2027-08-14','confirmed', now())""")
admin("insert into bookings (stamm, booked_by, arrive, depart, status, note) values ('uli','karlina','2027-09-04','2027-09-12','pending','Mit Freundin')")

# ---------- Fake-Supabase: Auth simuliert, Daten echt aus Postgres ----------
calls = []
kicks = []
VAPID_PUB = "BFzv_Yqo6hZduALmUIAwUSTw6NW83wNSjba9E2FXUL0ZcqQM-oqYpLsE68hkJoumhsLaQQTeNo_TbuF_cUyR8dY"
# iPhone-App vom Home-Bildschirm nachgestellt: Push-Abo, Erlaubnis-Abfrage und App-Symbol-Zähler
IOS_STUB = """
window.__badge = []; window.__perm = window.__perm || 'default'; window.__sub = null; window.__subscribeCalls = 0;
const fakeSub = { endpoint: 'https://web.push.apple.com/test-' + Math.random().toString(36).slice(2),
  toJSON() { return { endpoint: this.endpoint, keys: { p256dh: 'B' + 'x'.repeat(86), auth: 'a'.repeat(22) } }; },
  unsubscribe: async () => { window.__sub = null; return true; } };
const ask = () => { if (window.__perm === 'default') window.__perm = window.__answer || 'granted'; return window.__perm; };
const pm = { getSubscription: async () => window.__sub,
  subscribe: async o => { window.__subscribeCalls++; window.__key = o.applicationServerKey && o.applicationServerKey.length;
    if (ask() !== 'granted') throw new DOMException('denied', 'NotAllowedError'); window.__sub = fakeSub; return fakeSub; } };
const reg = { pushManager: pm };
Object.defineProperty(navigator, 'serviceWorker', { value: { register: async () => reg, ready: Promise.resolve(reg), addEventListener() {} }, configurable: true });
window.PushManager = function () {};
window.Notification = { get permission() { return window.__perm; }, requestPermission: async () => ask() };
navigator.setAppBadge = async n => { window.__badge.push(n); };
navigator.clearAppBadge = async () => { window.__badge.push(0); };
Object.defineProperty(navigator, 'standalone', { value: true, configurable: true });
"""
def email_of(req):
    a = req.headers.get("authorization", "")
    return a[len("Bearer tok:"):] if a.startswith("Bearer tok:") else None

async def handle(route):
    req = route.request; u = urlparse(req.url); path = u.path
    body = json.loads(req.post_data) if req.post_data else {}
    calls.append((req.method, path))
    def reply(status, data):
        return route.fulfill(status=status, content_type="application/json", body="" if data is None else json.dumps(data, default=str))
    if path == "/auth/v1/otp":
        if not admin("select 1 from people where email = lower(%s)", (body["email"],)):
            return await reply(500, {"code": 500, "error_code": "unexpected_failure", "msg": "Database error saving new user"})
        return await reply(200, {})
    if path == "/auth/v1/verify":
        if body.get("token") != "123456":
            return await reply(403, {"code": 403, "error_code": "otp_expired", "msg": "Token has expired or is invalid"})
        e = body["email"]
        return await reply(200, {"access_token": "tok:" + e, "refresh_token": "r:" + e, "expires_in": 3600, "expires_at": int(time.time()) + 3600, "user": {"email": e}})
    if path == "/auth/v1/token":
        e = body["refresh_token"][2:]
        return await reply(200, {"access_token": "tok:" + e, "refresh_token": "r:" + e, "expires_in": 3600, "expires_at": int(time.time()) + 3600, "user": {"email": e}})
    if path == "/auth/v1/logout":
        return await reply(204, None)
    if path == "/functions/v1/push":   # Server-Funktion: GET Schlüssel, POST = Versand anstoßen
        if req.method == "POST": kicks.append(time.time())
        return await reply(200, {"publicKey": VAPID_PUB} if req.method == "GET" else {"sent": 0})
    e = email_of(req)
    if not e: return await reply(401, {"message": "JWT missing"})
    if path == "/rest/v1/rpc/whoami":
        r, err = as_user(e, "select whoami()"); return await reply(200, r[0][0])
    if path == "/rest/v1/people":
        r, err = as_user(e, "select coalesce(json_agg(x order by x.sort), '[]') from (select id, name, stamm, is_super, sort from people) x")
        return await reply(200, r[0][0])
    if path == "/rest/v1/bookings":
        r, err = as_user(e, "select coalesce(json_agg(b order by b.arrive), '[]') from bookings b")
        return await reply(200, r[0][0])
    if path in ("/rest/v1/rpc/save_push_subscription", "/rest/v1/rpc/delete_push_subscription"):
        fn = path.rsplit("/", 1)[1]
        if fn == "save_push_subscription":
            r, err = as_user(e, "select save_push_subscription(%s, %s, %s)::text", (body["p_endpoint"], body["p_p256dh"], body["p_auth"]))
        else:
            r, err = as_user(e, "select delete_push_subscription(%s)::text", (body["p_endpoint"],))
        if err: return await reply(400, {"code": "P0001", "message": err})
        return await reply(200, None)
    m = re.match(r"/rest/v1/rpc/(create_booking|decide_booking|cancel_booking)$", path)
    if m:
        fn = m.group(1)
        if fn == "create_booking":
            r, err = as_user(e, "select row_to_json(x) from create_booking(%s, %s, %s, %s, %s) x",
                             (body["p_arrive"], body["p_depart"], body["p_companions"], body["p_guests"], body["p_note"]))
        elif fn == "decide_booking":
            r, err = as_user(e, "select row_to_json(x) from decide_booking(%s, %s, %s) x", (body["p_id"], body["p_verdict"], body["p_reason"]))
        else:
            r, err = as_user(e, "select row_to_json(x) from cancel_booking(%s) x", (body["p_id"],))
        if err: return await reply(400, {"code": "P0001", "message": err, "details": None, "hint": None})
        return await reply(200, r[0][0])
    return await reply(404, {"message": "unbekannt " + path})

# ---------- Lokaler Webserver für die Repo-Dateien ----------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8123), functools.partial(Quiet, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
APP = "http://127.0.0.1:8123/index.html"

async def new_ctx(browser, live=True, w=390, h=844, storage=None, dark=False, ios=None, ua=None):
    ctx = await browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                    reduced_motion="reduce", color_scheme="dark" if dark else "light", storage_state=storage, locale="de-DE",
                                    **({"user_agent": ua} if ua else {}))
    if live: await ctx.add_init_script("window.CASA_FORCE_LIVE = true;")
    if ios: await ctx.add_init_script(ios)
    await ctx.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=""))
    await ctx.route("https://fonts.gstatic.com/**", lambda r: r.abort())
    await ctx.route(SB + "/**", handle)
    page = await ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    return ctx, page, errors

async def login(page, email, code="123456"):
    await page.goto(APP)
    await page.wait_for_selector('#login [name="email"]')
    await page.fill('#login [name="email"]', email)
    await page.click('#login [type="submit"]')
    await page.wait_for_selector('#login [name="code"]', timeout=4000)
    await page.fill('#login [name="code"]', code)   # 6 Ziffern -> sendet automatisch

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/usr/bin/google-chrome")

        print("Anmeldung")
        ctx, page, errs = await new_ctx(browser)
        await page.goto(APP)
        await page.wait_for_selector('#login [name="email"]')
        check("Ohne Sitzung erscheint die Anmeldung", await page.is_visible("#login h1"))
        await page.screenshot(path=f"{SHOTS}/live-01-login.png")
        await page.fill('#login [name="email"]', "fremd@y.de"); await page.click('#login [type="submit"]')
        await page.wait_for_selector("#login .err")
        t = await page.inner_text("#login .err")
        check("Unbekannte E-Mail: klare Meldung", "nicht freigeschaltet" in t, t)
        await page.fill('#login [name="email"]', "Leon@X.de"); await page.click('#login [type="submit"]')
        await page.wait_for_selector('#login [name="code"]')
        check("Code-Schritt zeigt Adresse (kleingeschrieben)", "leon@x.de" in await page.inner_text("#login .lead"))
        check("Neuer Code erst nach Wartezeit", await page.is_disabled('[data-lg="resend"]'))
        await page.screenshot(path=f"{SHOTS}/live-02-code.png")
        await page.fill('#login [name="code"]', "000000")
        await page.wait_for_selector("#login .err")
        t = await page.inner_text("#login .err")
        check("Falscher Code: klare Meldung", "stimmt nicht" in t, t)
        await page.fill('#login [name="code"]', "123456")
        await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        await page.wait_for_timeout(700)
        check("Nach Code: Übersicht mit Namen", "Leon" in await page.inner_text("#v-home .hello h1"))
        check("Anmeldeebene verschwunden", await page.is_hidden("#login"))
        home_txt = await page.inner_text("#v-home")
        check("Hausstatus aus echten Daten", "Haus frei" in home_txt or "im Haus" in home_txt, home_txt[:120])
        fits = await page.evaluate("(() => { const v = document.getElementById('v-home'); return v.scrollHeight - v.clientHeight; })()")
        check("Übersicht ohne Scrollen (390×844)", fits == 0, fits)
        await page.screenshot(path=f"{SHOTS}/live-03-home.png")

        print("Buchen als Sub-User")
        await page.click('[data-act="plan"]')
        await page.evaluate("(() => { const p = document.getElementById('pager'); p.scrollLeft = p.clientWidth * 18; })()")
        await page.wait_for_timeout(400)
        await page.click('#v-cal [data-day="2027-07-14"]')
        await page.wait_for_timeout(200)
        await page.click('#v-cal [data-day="2027-07-21"]')
        await page.wait_for_selector('.layer [data-act="submit"]')
        await page.wait_for_timeout(500)
        btxt = await page.inner_text('.layer [data-act="submit"]')
        check("Sub-User sieht 'Reservieren und Freigabe anfragen'", "Freigabe" in btxt, btxt)
        hsw = await page.evaluate("(() => { const e = document.querySelector('.layer [data-hs]'); return e && !e.hidden ? e.innerText : ''; })()")
        check("Hochsaison-Warnung im Planen-Sheet", "Hochsaison" in hsw and "Micha, Uli und Fanny" in hsw, hsw)
        sub = await page.inner_text("#cal-sub")
        check("Kalender-Kopf zeigt Hochsaison im Juli", "Hochsaison" in sub and "28.6." in sub, sub)
        hscells = await page.evaluate("document.querySelectorAll('#v-cal .c.hs[data-day^=\"2027-07\"]').length")
        check("Alle 31 Julitage als Hochsaison markiert", hscells == 31, hscells)
        await page.screenshot(path=f"{SHOTS}/live-04-plan.png")
        await page.click('.layer [data-act="submit"]')
        await page.wait_for_selector("#toast.on", timeout=4000)
        t = await page.inner_text("#toast")
        check("Toast 'Reserviert' nennt alle drei", "Reserviert" in t and "Micha, Uli und Fanny geben frei" in t, t)
        r = admin("select status, booked_by from bookings where arrive = '2027-07-14'")
        check("In der Datenbank als pending von leon", r == [("pending", "leon")], r)

        print("Konflikt: Daten veraltet, Server lehnt ab")
        admin("insert into bookings (stamm, booked_by, arrive, depart, status, decided_at) values ('fanny','fanny','2027-10-10','2027-10-20','confirmed', now())")
        await page.wait_for_timeout(2600)   # Toast ausblenden lassen
        await page.evaluate("(() => { const p = document.getElementById('pager'); p.scrollLeft = p.clientWidth * 21; })()")
        await page.wait_for_timeout(400)
        await page.click('#v-cal [data-day="2027-10-12"]'); await page.wait_for_timeout(200)
        await page.click('#v-cal [data-day="2027-10-15"]')
        await page.wait_for_selector('.layer [data-act="submit"]'); await page.wait_for_timeout(500)
        await page.click('.layer [data-act="submit"]')
        await page.wait_for_selector(".layer [data-err] .err", timeout=4000)
        t = await page.inner_text(".layer [data-err] .err")
        check("Server-Konflikt verständlich im Sheet", "Überschneidet sich mit Fanny" in t, t)
        await page.wait_for_timeout(600)
        dis = await page.is_disabled('.layer [data-act="submit"]')
        check("Nach Neuladen ist Buchen-Button gesperrt", dis)
        await page.screenshot(path=f"{SHOTS}/live-05-conflict.png")
        await page.click(".layer .x-btn"); await page.wait_for_timeout(500)

        print("Sitzung bleibt, Cache-Start")
        state = await ctx.storage_state()
        check("Keine Fehler in der Konsole (Leon)", not errs, errs[:3])
        await ctx.close()
        ctx, page, errs = await new_ctx(browser, storage=state)
        n_before = len(calls)
        await page.goto(APP)
        await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        check("Neu öffnen: direkt in der App, kein Login", await page.is_hidden("#login"))
        await page.wait_for_timeout(500)
        check("…und im Hintergrund aktualisiert", any(c[1] == "/rest/v1/bookings" for c in calls[n_before:]))

        print("Konto und Abmelden")
        await page.click('#v-home [data-act="who"]')
        await page.wait_for_selector('.layer [data-act="logout"]')
        acct = await page.inner_text(".layer")
        check("Konto zeigt Mail und Stamm", "leon@x.de" in acct and "Michas Familie" in acct, acct[:150])
        await page.screenshot(path=f"{SHOTS}/live-06-account.png")
        await page.click('.layer [data-act="logout"]'); await page.click('.layer [data-act="logout"]')
        await page.wait_for_selector('#login [name="email"]', timeout=3000)
        sess = await page.evaluate("localStorage.getItem('casa-la-paz.session.v1')")
        cache = await page.evaluate("localStorage.getItem('casa-la-paz.cache.v1')")
        check("Abmelden löscht Sitzung und Zwischenspeicher", not sess and not cache, (sess, cache))
        await ctx.close()

        print("Freigeben als Super-User eines anderen Stamms")
        ctx, page, errs = await new_ctx(browser)
        await login(page, "micha@x.de")
        await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        badge = await page.inner_text("#badge")
        check("Badge zeigt 2 (Karlina + Leon, weil Hochsaison)", badge.strip() == "2", badge)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(500)
        await page.screenshot(path=f"{SHOTS}/live-07-requests.png")
        await page.click('#v-req [data-approve]')
        await page.wait_for_selector("#toast.on", timeout=4000)
        t = await page.inner_text("#toast")
        check("Toast 'Freigegeben: Karlina'", "Freigegeben" in t and "Karlina" in t, t)
        r = admin("select status, decided_by from bookings where booked_by = 'karlina'")
        check("In der Datenbank freigegeben von micha", r == [("confirmed", "micha")], r)
        await page.wait_for_timeout(2900)
        rowtxt = await page.inner_text("#v-req .req-hs")
        check("Anfrage zeigt Hochsaison und 0 von 3", "Hochsaison" in rowtxt and "0 von 3" in rowtxt, rowtxt)
        await page.click('#v-req [data-approve]')
        await page.wait_for_selector("#toast.on", timeout=4000)
        t = await page.inner_text("#toast")
        check("Teil-Freigabe: Toast nennt, wer fehlt", "fehlen noch Uli und Fanny" in t, t)
        r = admin("select status, jsonb_array_length(approvals) from bookings where arrive = '2027-07-14'")
        check("DB: weiter pending, 1 Freigabe", r == [("pending", 1)], r)
        await page.wait_for_timeout(600)
        await page.screenshot(path=f"{SHOTS}/live-08-hs-partial.png")
        check("Keine Fehler in der Konsole (Micha)", not errs, errs[:3])
        await ctx.close()

        print("Freigabe-Wettlauf: Fanny und Uli gleichzeitig (außerhalb der Hochsaison)")
        admin("insert into bookings (stamm, booked_by, arrive, depart, status) values ('micha','leon','2027-11-03','2027-11-06','pending')")
        cf, pf, _ = await new_ctx(browser); await login(pf, "fanny@x.de"); await pf.wait_for_selector("#v-home .hello h1", timeout=5000)
        cu, pu, _ = await new_ctx(browser); await login(pu, "uli@x.de"); await pu.wait_for_selector("#v-home .hello h1", timeout=5000)
        await pf.click('.tab[data-tab="req"]'); await pu.click('.tab[data-tab="req"]'); await pf.wait_for_timeout(400)
        ids = admin("select id::text from bookings where arrive = '2027-11-03'")[0][0]
        await pf.click(f'#v-req [data-approve="{ids}"]'); await pf.wait_for_selector("#toast.on", timeout=4000)
        await pu.click(f'#v-req [data-reject="{ids}"]'); await pu.wait_for_selector("#reject-reason")
        await pu.fill("#reject-reason", "Da ist das Dach dran"); await pu.click('[data-act="do-reject"]')
        await pu.wait_for_selector("#toast.on", timeout=4000)
        t = await pu.inner_text("#toast")
        check("Zweite Entscheidung bekommt klare Meldung", "schon entschieden" in t, t)
        r = admin("select status, decided_by from bookings where arrive = '2027-11-03'")
        check("Erste Entscheidung (Fanny) gilt", r == [("confirmed", "fanny")], r)
        await cf.close(); await cu.close()

        print("Mitteilungen")
        admin("delete from push_subscriptions")
        admin("delete from bookings where status = 'pending'")
        admin("insert into bookings (stamm, booked_by, arrive, depart, status) values ('uli','kaspar','2027-10-04','2027-10-08','pending')")
        ctx, page, errs = await new_ctx(browser, ios=IOS_STUB)
        await login(page, "micha@x.de"); await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        await page.wait_for_timeout(400)
        bg = await page.evaluate("getComputedStyle(document.getElementById('badge')).backgroundColor")
        check("Zähler am Reiter in iOS-Rot (nicht in Ulis Familienfarbe)", bg == "rgb(255, 59, 48)", bg)
        check("Ohne Erlaubnis kein App-Symbol-Zähler", await page.evaluate("window.__badge.length") == 0)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(400)
        check("Karte 'Neue Anfragen sofort sehen' für Super-User", await page.is_visible("#notif-card"))
        await page.screenshot(path=f"{SHOTS}/live-09-notif-card.png")
        await page.click('#notif-card [data-act="notif-on"]')
        await page.wait_for_selector("#toast.on", timeout=4000)
        t = await page.inner_text("#toast")
        check("Einschalten: Toast 'Mitteilungen sind an'", "Mitteilungen sind an" in t, t)
        check("Abfrage direkt über subscribe() mit Schlüssel (65 Byte)", await page.evaluate("window.__subscribeCalls") == 1 and await page.evaluate("window.__key") == 65)
        r = admin("select person_id from push_subscriptions")
        check("Gerät in der Datenbank für Micha", r == [("micha",)], r)
        check("Karte verschwindet", await page.locator("#notif-card").count() == 0)
        nb = await page.inner_text("#badge")
        check("App-Symbol-Zähler = Zähler am Reiter", await page.evaluate("window.__badge[window.__badge.length - 1]") == int(nb), (nb, await page.evaluate("window.__badge")))
        await page.click('#v-req [data-act="who"]'); await page.wait_for_selector("#acct-notif")
        at = await page.inner_text("#acct-notif")
        check("Konto: Mitteilungen 'An'", "An" in at and "ausschalten" in at, at)
        await page.screenshot(path=f"{SHOTS}/live-10-account-notif.png")
        await page.click(".layer .x-btn"); await page.wait_for_timeout(500)
        before = await page.evaluate("window.__badge[window.__badge.length - 1]")
        k0 = len(kicks)
        await page.click('#v-req [data-approve]'); await page.wait_for_selector("#toast.on", timeout=4000); await page.wait_for_timeout(600)
        after = await page.evaluate("window.__badge[window.__badge.length - 1]")
        check("Nach Freigabe sinkt der App-Symbol-Zähler", after == before - 1, (before, after))
        check("Finale Freigabe stößt Mitteilung an Kaspar an", len(kicks) == k0 + 1, (k0, len(kicks)))
        mstate = await ctx.storage_state()
        check("Keine Fehler in der Konsole (Mitteilungen Micha)", not errs, errs[:3])
        await ctx.close()

        ctx, page, errs = await new_ctx(browser, ios=IOS_STUB)
        await login(page, "leon@x.de"); await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(300)
        ct = await page.inner_text("#notif-card")
        check("Sub-User: Karte 'Bescheid bekommen'", "Bescheid bekommen" in ct and "freigegeben oder abgelehnt" in ct, ct)
        await page.screenshot(path=f"{SHOTS}/live-11-notif-sub.png")
        await page.click('#notif-card [data-act="notif-on"]'); await page.wait_for_selector("#toast.on", timeout=4000)
        check("Sub-User kann einschalten, Gerät gespeichert", admin("select count(*) from push_subscriptions where person_id = 'leon'") == [(1,)])
        await page.click('#v-req [data-act="who"]'); await page.wait_for_selector("#acct-notif")
        at = await page.inner_text("#acct-notif")
        check("Sub-User: Konto erklärt Entscheidungs-Mitteilung", "An" in at and "freigegeben ist" in at, at)
        await page.click(".layer .x-btn"); await page.wait_for_timeout(500)
        n0 = len(kicks)
        await page.click('.tab[data-tab="home"]'); await page.wait_for_timeout(300)
        await page.click('#v-home [data-act="plan"]'); await page.wait_for_timeout(300)
        await page.evaluate("(() => { const p = document.getElementById('pager'); p.scrollLeft = p.clientWidth * 22; })()"); await page.wait_for_timeout(400)
        await page.click('#v-cal [data-day="2027-11-20"]'); await page.wait_for_timeout(200)
        await page.click('#v-cal [data-day="2027-11-23"]')
        await page.wait_for_selector('.layer [data-act="submit"]'); await page.wait_for_timeout(500)
        await page.click('.layer [data-act="submit"]'); await page.wait_for_selector("#toast.on", timeout=4000)
        await page.wait_for_timeout(300)
        check("Neue Anfrage stößt den Versand an (POST /functions/v1/push)", len(kicks) == n0 + 1, (n0, len(kicks)))
        await ctx.close()

        ctx, page, errs = await new_ctx(browser, ios=IOS_STUB.replace("window.__perm || 'default'", "'default'") + "window.__answer = 'denied';")
        await login(page, "fanny@x.de"); await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(300)
        await page.click('#notif-card [data-act="notif-on"]'); await page.wait_for_selector("#toast.on", timeout=4000)
        t = await page.inner_text("#toast")
        check("Nicht erlaubt: Hinweis auf iPhone-Einstellungen", "Einstellungen" in t, t)
        await page.click('#v-req [data-act="who"]'); await page.wait_for_selector("#acct-notif")
        at = await page.inner_text("#acct-notif")
        check("Konto: 'Am iPhone aus' mit Weg in den Einstellungen", "Am iPhone aus" in at and "Kennzeichen" in at, at)
        check("Kein Gerät für Fanny gespeichert", admin("select count(*) from push_subscriptions where person_id = 'fanny'") == [(0,)])
        check("Keine Fehler in der Konsole (Fanny)", not errs, errs[:3])
        await ctx.close()

        IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
        ctx, page, errs = await new_ctx(browser, ua=IPHONE, ios="delete window.PushManager;")
        await login(page, "uli@x.de"); await page.wait_for_selector("#v-home .hello h1", timeout=5000)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(300)
        check("Safari statt Home-Bildschirm: keine Karte", await page.locator("#notif-card").count() == 0)
        await page.click('#v-req [data-act="who"]'); await page.wait_for_selector("#acct-notif")
        at = await page.inner_text("#acct-notif")
        check("Safari: Konto erklärt 'Nur in der App'", "Nur in der App" in at and "Home-Bildschirm" in at, at)
        await ctx.close()

        ctx, page, errs = await new_ctx(browser, storage=mstate, ios=IOS_STUB.replace("window.__perm || 'default'", "'granted'") + "window.__sub = null;")
        await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=4000); await page.wait_for_timeout(600)
        check("Neustart mit Erlaubnis: Zähler am Symbol wird gesetzt", len(await page.evaluate("window.__badge")) > 0)
        await page.click('#v-home [data-act="who"]'); await page.wait_for_selector("#acct-notif")
        await page.click('.layer [data-act="notif-on"]'); await page.wait_for_selector("#toast.on", timeout=4000)
        n = admin("select count(*) from push_subscriptions where person_id = 'micha'")[0][0]
        check("Zweites Gerät für Micha", n == 2, n)
        await page.wait_for_timeout(300)
        await page.click('.layer [data-act="logout"]'); await page.click('.layer [data-act="logout"]')
        await page.wait_for_selector('#login [name="email"]', timeout=4000)
        n = admin("select count(*) from push_subscriptions where person_id = 'micha'")[0][0]
        check("Abmelden meldet dieses Gerät ab (anderes bleibt)", n == 1, n)
        check("Abmelden löscht den Zähler am Symbol", await page.evaluate("window.__badge[window.__badge.length - 1]") == 0)
        await ctx.close()

        print("Service Worker (echtes Chrome): Push-Ereignis zeigt Mitteilung")
        ctx, page, errs = await new_ctx(browser, live=False)
        await ctx.grant_permissions(["notifications"], origin="http://127.0.0.1:8123")
        await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        await page.evaluate("navigator.serviceWorker.register('sw.js').then(() => navigator.serviceWorker.ready)")
        cdp = await ctx.new_cdp_session(page)
        regs = []
        cdp.on("ServiceWorker.workerRegistrationUpdated", lambda ev: regs.extend(ev["registrations"]))
        await cdp.send("ServiceWorker.enable"); await page.wait_for_timeout(500)
        rid = next((r["registrationId"] for r in regs if r["scopeURL"].startswith("http://127.0.0.1:8123/")), None)
        check("sw.js registriert", rid is not None, regs)
        if rid:
            await cdp.send("ServiceWorker.deliverPushMessage", {"origin": "http://127.0.0.1:8123", "registrationId": rid,
                "data": json.dumps({"title": "Neue Anfrage von Leon", "body": "17.–25. Juli 2027 · 8 Nächte", "badge": 2, "tag": "b1", "url": "./#anfragen"})})
            await page.wait_for_timeout(800)
            notes = await page.evaluate("navigator.serviceWorker.ready.then(r => r.getNotifications()).then(l => l.map(n => [n.title, n.body, n.tag, n.data && n.data.url]))")
            check("Mitteilung mit Titel, Text, Tag und Ziel", notes == [["Neue Anfrage von Leon", "17.–25. Juli 2027 · 8 Nächte", "b1", "./#anfragen"]], notes)
            await cdp.send("ServiceWorker.deliverPushMessage", {"origin": "http://127.0.0.1:8123", "registrationId": rid,
                "data": json.dumps({"title": "Neue Anfrage von Leon", "body": "geändert", "badge": 1, "tag": "b1"})})
            await page.wait_for_timeout(800)
            notes = await page.evaluate("navigator.serviceWorker.ready.then(r => r.getNotifications()).then(l => l.map(n => n.body))")
            check("Gleiche Anfrage ersetzt die Mitteilung (kein Stapel)", notes == ["geändert"], notes)
        sw = open(os.path.join(ROOT, "sw.js"), encoding="utf-8").read()
        check("sw.js speichert nichts zwischen (kein fetch-Handler)", '"fetch"' not in sw and "caches" not in sw)
        await ctx.close()

        print("Werkbank: Karte als Vorschau")
        ctx, page, errs = await new_ctx(browser, live=False)
        await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        await page.click('#v-home [data-act="who"]'); await page.wait_for_selector('.layer [data-me="uli"]')
        await page.click('.layer [data-me="uli"]'); await page.wait_for_timeout(700)
        await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(300)
        check("Werkbank: Karte für Super-User sichtbar", await page.is_visible("#notif-card"))
        await page.click('#notif-card [data-act="notif-on"]'); await page.wait_for_selector("#toast.on", timeout=3000)
        check("Werkbank: Einschalten erklärt Vorschau", "echten App" in await page.inner_text("#toast"))
        await page.click('#notif-card [data-act="notif-later"]'); await page.wait_for_timeout(300)
        check("'Später' blendet die Karte aus", await page.locator("#notif-card").count() == 0)
        await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(300)
        check("…auch nach Neuladen", await page.locator("#notif-card").count() == 0)
        await ctx.close()
        for (w, h, dark, name) in [(375, 560, False, "560"), (390, 844, True, "dark")]:
            ctx, page, errs = await new_ctx(browser, live=False, w=w, h=h, dark=dark)
            await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
            await page.click('#v-home [data-act="who"]'); await page.wait_for_selector('.layer [data-me="micha"]')
            await page.click('.layer [data-me="micha"]'); await page.wait_for_timeout(700)
            await page.goto(APP); await page.wait_for_selector("#v-home .hello h1", timeout=3000)
            await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(500)
            await page.screenshot(path=f"{SHOTS}/notif-card-{name}.png")
            await ctx.close()

        print("Kleine Bildschirme + Dunkelmodus")
        for (w, h, dark, name) in [(390, 640, False, "640"), (375, 560, False, "560"), (390, 844, True, "dark")]:
            ctx, page, errs = await new_ctx(browser, w=w, h=h, dark=dark)
            await page.goto(APP); await page.wait_for_selector('#login [name="email"]')
            await page.screenshot(path=f"{SHOTS}/live-login-{name}.png")
            vis = await page.evaluate("(() => { const b = document.querySelector('#login [type=submit]').getBoundingClientRect(); return b.bottom <= innerHeight; })()")
            check(f"Login-Button sichtbar ({name})", vis)
            await ctx.close()

        print("Werkbank (Demo-Modus) unverändert")
        ctx, page, errs = await new_ctx(browser, live=False)
        await page.goto(APP)
        await page.wait_for_selector("#v-home .hello h1", timeout=3000)
        check("Demo startet ohne Login", await page.is_hidden("#login"))
        await page.click('#v-home [data-act="who"]'); await page.wait_for_selector(".layer [data-me]")
        check("Rollenwechsel vorhanden", await page.locator(".layer [data-me]").count() == 10)
        await page.click('.layer [data-me="micha"]'); await page.wait_for_timeout(600)
        await page.click('.tab[data-tab="req"]'); await page.wait_for_timeout(400)
        await page.click('#v-req [data-approve]'); await page.wait_for_selector("#toast.on")
        t = await page.inner_text("#toast")
        check("Demo: Hochsaison-Freigabe (Fanny hatte schon, jetzt Micha, es fehlt Uli)", "fehlt noch Uli" in t, t)
        live_calls = [c for c in calls if c[0]]  # nur zur Info
        await page.click('.layer [data-close]') if await page.locator('.layer [data-close]').count() else None
        await page.click('#v-req [data-act="who"]'); await page.wait_for_selector('.layer [data-me="leon"]')
        await page.click('.layer [data-me="leon"]'); await page.wait_for_timeout(600)
        await page.click('.tab[data-tab="cal"]'); await page.wait_for_timeout(300)
        await page.evaluate("(() => { const p = document.getElementById('pager'); p.scrollLeft = p.clientWidth * 21; })()"); await page.wait_for_timeout(400)
        await page.click('#v-cal [data-day="2027-10-01"]'); await page.wait_for_timeout(2900)
        bartxt = await page.inner_text("#selbar")
        check("Hinweisleiste nennt späteste Abreise (1.10. + 31 Nächte = 1.11.)", "1. November" in bartxt, bartxt)
        await page.evaluate("(() => { const p = document.getElementById('pager'); p.scrollLeft = p.clientWidth * 22; })()"); await page.wait_for_timeout(400)
        nogo = await page.evaluate("document.querySelector('#v-cal .c[data-day=\"2027-11-03\"]').classList.contains('nogo')")
        check("Tage nach 31 Nächten ausgegraut", nogo)
        await page.click('#v-cal [data-day="2027-11-03"]'); await page.wait_for_selector("#toast.on", timeout=3000)
        t = await page.inner_text("#toast")
        check("Toast bei mehr als 31 Nächten", "Höchstens 31 Nächte" in t, t)
        check("Keine Fehler in der Konsole (Demo)", not [e for e in errs if "manifest" not in e and "icon" not in e], errs[:3])
        await ctx.close()
        await browser.close()
    srv.shutdown()
    print(f"\n{ok} ok, {fail} fehlgeschlagen")
    sys.exit(1 if fail else 0)

asyncio.run(main())
