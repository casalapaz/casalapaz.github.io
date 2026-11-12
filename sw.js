/* Casa la Paz – Service Worker nur für Mitteilungen.
   Bewusst KEIN fetch-Handler und kein Zwischenspeicher: die App lädt immer frisch vom Server,
   Updates kommen wie bisher über version.json. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : "" }; }
  const jobs = [self.registration.showNotification(d.title || "Casa la Paz", {
    body: d.body || "",
    tag: d.tag || undefined,
    icon: "icons/icon-192.png?v=3",
    data: { url: d.url || "./#anfragen" }
  })];
  // Zähler am App-Symbol (wie bei Mail). iOS: nur in der App vom Home-Bildschirm, mit erlaubten Mitteilungen.
  if (typeof d.badge === "number" && self.navigator.setAppBadge) {
    jobs.push((d.badge > 0 ? self.navigator.setAppBadge(d.badge) : self.navigator.clearAppBadge()).catch(() => {}));
  }
  e.waitUntil(Promise.all(jobs));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./#anfragen", self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
    for (const c of list) {
      if ("focus" in c) { c.postMessage({ type: "open", url }); return c.focus(); }
    }
    return self.clients.openWindow(url);
  }));
});
