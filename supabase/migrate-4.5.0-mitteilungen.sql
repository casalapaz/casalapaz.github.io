-- ---------------------------------------------------------------------
-- Mitteilungen (seit 4.4.0, erweitert 4.5.0):
--   * neue Anfrage  → Push an die Super-User, deren Freigabe fehlt
--   * fertig entschieden (alle nötigen Freigaben da, oder abgelehnt)
--                   → Push an die Person, die angefragt hat
--   * Zähler am App-Symbol = Anfragen, die auf die Person warten
-- Versand macht die Server-Funktion "push" (supabase/functions/push),
-- die nur push_due/push_report benutzt. Ersetzt migrate-4.4.0 vollständig,
-- lässt sich vor oder nach 4.4.0 und beliebig oft ausführen.
-- ---------------------------------------------------------------------
create table if not exists public.push_subscriptions (
  endpoint   text primary key check (endpoint ~ '^https://' and length(endpoint) <= 1000),
  person_id  text not null references public.people (id) on delete cascade,
  p256dh     text not null check (length(p256dh) between 40 and 200),
  auth       text not null check (length(auth) between 10 and 100),
  created_at timestamptz not null default now(),
  last_ok    timestamptz
);
alter table public.push_subscriptions enable row level security;

-- Wer wurde zu welcher neuen Anfrage schon benachrichtigt (jede Anfrage höchstens einmal pro Person).
create table if not exists public.push_sent (
  booking_id uuid not null references public.bookings (id) on delete cascade,
  person_id  text not null references public.people (id) on delete cascade,
  sent_at    timestamptz not null default now(),
  primary key (booking_id, person_id)
);
alter table public.push_sent enable row level security;

-- Wurde die anfragende Person über die Entscheidung benachrichtigt? (einmal pro Anfrage)
create table if not exists public.push_decided (
  booking_id uuid primary key references public.bookings (id) on delete cascade,
  sent_at    timestamptz not null default now()
);
alter table public.push_decided enable row level security;

-- Wartet die Anfrage auf die Entscheidung dieser Person? (= canApprove in index.html)
create or replace function public.awaits_decision(p public.people, b public.bookings) returns boolean
language sql stable set search_path = public as $$
  select p.is_super and b.status = 'pending'
     and not (b.approvals @> jsonb_build_array(jsonb_build_object('by', p.id)))
     and (b.high_season or p.stamm <> b.stamm)
$$;

-- Entscheidung, über die die anfragende Person benachrichtigt wird: von jemand anderem
-- freigegeben (alle nötigen Freigaben) oder abgelehnt. Super-User-Buchungen (decided_by leer)
-- und Stornos zählen nicht.
create or replace function public.decision_to_report(b public.bookings) returns boolean
language sql stable set search_path = public as $$
  select b.status in ('confirmed', 'rejected') and b.decided_by is not null and b.decided_by <> b.booked_by
$$;

-- App: dieses Gerät für Mitteilungen anmelden. Bereits offene Anfragen und schon entschiedene
-- eigene Anfragen gelten als gemeldet, damit nach dem Einschalten keine Flut alter Mitteilungen kommt.
create or replace function public.save_push_subscription(p_endpoint text, p_p256dh text, p_auth text) returns void
language plpgsql security definer set search_path = public as $$
declare me public.people;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  perform public.expire_pending();
  insert into public.push_subscriptions (endpoint, person_id, p256dh, auth)
  values (p_endpoint, me.id, p_p256dh, p_auth)
  on conflict (endpoint) do update set person_id = excluded.person_id, p256dh = excluded.p256dh, auth = excluded.auth;
  -- höchstens 5 Geräte pro Person, das älteste fliegt raus
  delete from public.push_subscriptions where endpoint in (
    select endpoint from public.push_subscriptions where person_id = me.id order by created_at desc offset 5);
  insert into public.push_sent (booking_id, person_id)
  select b.id, me.id from public.bookings b where public.awaits_decision(me, b)
  on conflict do nothing;
  insert into public.push_decided (booking_id)
  select b.id from public.bookings b where b.booked_by = me.id and public.decision_to_report(b)
  on conflict do nothing;
end $$;

create or replace function public.delete_push_subscription(p_endpoint text) returns void
language plpgsql security definer set search_path = public as $$
declare me public.people;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  delete from public.push_subscriptions where endpoint = p_endpoint and person_id = me.id;
end $$;

-- Server-Funktion: alles, was jetzt verschickt werden muss (eine Zeile pro Gerät).
--   kind = 'request'   neue Anfrage an einen Super-User
--   kind = 'confirmed' / 'rejected'  Entscheidung an die anfragende Person
--   approvers = Namen in Reihenfolge der Freigaben, decided_by = wer abgelehnt bzw. zuletzt freigegeben hat
drop function if exists public.push_due();
create function public.push_due()
returns table (kind text, booking_id uuid, person_id text, endpoint text, p256dh text, auth text,
               booked_by text, arrive date, depart date, high_season boolean, open_count int,
               approvers text[], decided_by text, reason text)
language plpgsql security definer set search_path = public as $$
begin
  perform public.expire_pending();
  return query
    with req as (
      select 'request'::text as k, b.id, p.id as pid, b.arrive, b.depart, b.high_season, b.booked_by, b.decided_by, b.reason, b.approvals
        from public.bookings b
        join public.people p on public.awaits_decision(p, b)
       where not exists (select 1 from public.push_sent s where s.booking_id = b.id and s.person_id = p.id)
    ), dec as (
      select b.status::text as k, b.id, b.booked_by as pid, b.arrive, b.depart, b.high_season, b.booked_by, b.decided_by, b.reason, b.approvals
        from public.bookings b
       where public.decision_to_report(b)
         and b.decided_at > now() - interval '3 days'          -- nichts Altes nachliefern
         and not exists (select 1 from public.push_decided x where x.booking_id = b.id)
    ), due as (
      select * from req union all select * from dec
    ), open as (
      select p.id as pid, count(b.id)::int as n
        from public.people p join public.bookings b on public.awaits_decision(p, b)
       group by p.id
    )
    select d.k, d.id, d.pid, s.endpoint, s.p256dh, s.auth, pb.name, d.arrive, d.depart, d.high_season, coalesce(o.n, 0),
           coalesce((select array_agg(pa.name order by a.i)
                       from jsonb_array_elements(d.approvals) with ordinality a(x, i)
                       join public.people pa on pa.id = a.x ->> 'by'), '{}'),
           pd.name, d.reason
      from due d
      join public.push_subscriptions s on s.person_id = d.pid
      join public.people pb on pb.id = d.booked_by
      left join public.people pd on pd.id = d.decided_by
      left join open o on o.pid = d.pid
     order by d.pid, d.arrive;
end $$;

-- Server-Funktion: Ergebnis des Versands zurückmelden.
--   p_sent: [{"kind": "request|confirmed|rejected", "booking_id": "…", "person_id": "…"}] – zugestellt (mind. ein Gerät)
--   p_gone: Geräte, die Apple/Google nicht mehr kennt (abgemeldet, App gelöscht)
--   p_ok:   Geräte, die angenommen haben
create or replace function public.push_report(p_sent jsonb, p_gone text[], p_ok text[]) returns void
language plpgsql security definer set search_path = public as $$
begin
  insert into public.push_sent (booking_id, person_id)
  select (x ->> 'booking_id')::uuid, x ->> 'person_id' from jsonb_array_elements(coalesce(p_sent, '[]'::jsonb)) x
   where coalesce(x ->> 'kind', 'request') = 'request'
  on conflict do nothing;
  insert into public.push_decided (booking_id)
  select (x ->> 'booking_id')::uuid from jsonb_array_elements(coalesce(p_sent, '[]'::jsonb)) x
   where x ->> 'kind' in ('confirmed', 'rejected')
  on conflict do nothing;
  delete from public.push_subscriptions where endpoint = any (coalesce(p_gone, '{}'));
  update public.push_subscriptions set last_ok = now() where endpoint = any (coalesce(p_ok, '{}'));
end $$;

revoke all on public.push_subscriptions, public.push_sent, public.push_decided from anon, authenticated;
revoke execute on function public.awaits_decision(public.people, public.bookings), public.decision_to_report(public.bookings), public.save_push_subscription(text, text, text),
  public.delete_push_subscription(text), public.push_due(), public.push_report(jsonb, text[], text[]) from public, anon, authenticated;
grant execute on function public.save_push_subscription(text, text, text), public.delete_push_subscription(text) to authenticated;
grant execute on function public.push_due(), public.push_report(jsonb, text[], text[]) to service_role;
