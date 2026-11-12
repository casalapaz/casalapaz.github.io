-- =====================================================================
-- Casa la Paz · Datenbank-Einrichtung (Supabase)
-- Einmal komplett in Supabase > SQL Editor einfügen und "Run" drücken.
-- Lässt sich gefahrlos erneut ausführen (legt nichts doppelt an,
-- löscht keine Buchungen).
--
-- Die Regeln der App leben HIER, nicht nur in der App:
--   * Haus pro Zeitraum exklusiv für eine Familie (intern: stamm) (Ausschlussbedingung)
--   * Super-User buchen bestätigt, Sub-User reservieren + brauchen Freigabe
--   * Freigeben nur Super-User eines anderen Stamms, Ablehnen nur mit Begründung
--   * Hochsaison (Juli/August + Sommerferien NRW/HE/HH): alle Super-User müssen freigeben
--   * Erste Entscheidung je Person gilt, ein Nein reicht, offene Anfragen verfallen nach 21 Tagen
--   * Nur Personen aus der Tabelle "people" können sich anmelden
-- =====================================================================

create extension if not exists btree_gist with schema extensions;

-- ---------------------------------------------------------------------
-- Personen
-- ---------------------------------------------------------------------
create table if not exists public.people (
  id        text primary key check (id ~ '^[a-z0-9_-]{2,30}$'),
  name      text not null check (length(trim(name)) between 1 and 40),
  stamm     text not null check (stamm in ('micha', 'uli', 'fanny')),
  is_super  boolean not null default false,
  email     text unique check (email is null or email = lower(trim(email))),
  sort      int not null default 0
);

-- Super-User sind ausschließlich die drei Stammeltern.
create unique index if not exists people_one_super_per_stamm on public.people (stamm) where is_super;

-- ---------------------------------------------------------------------
-- Buchungen
-- ---------------------------------------------------------------------
create table if not exists public.bookings (
  id          uuid primary key default gen_random_uuid(),
  stamm       text not null check (stamm in ('micha', 'uli', 'fanny')),
  booked_by   text not null references public.people (id),
  companions  text[] not null default '{}',
  guests      int  not null default 0 check (guests between 0 and 12),
  note        text not null default '' check (length(note) <= 500),
  arrive      date not null,
  depart      date not null,                         -- Abreisetag (exklusiv)
  status      text not null check (status in ('confirmed', 'pending', 'rejected', 'expired', 'cancelled')),
  created_at  timestamptz not null default now(),
  decided_by  text references public.people (id),
  decided_at  timestamptz,
  reason      text not null default '' check (length(reason) <= 500),
  check (depart > arrive),
  check (status <> 'rejected' or length(trim(reason)) >= 3)
);

-- Kernregel: aktive Aufenthalte verschiedener Stämme dürfen sich nicht überschneiden.
-- '[)' = Abreisetag zählt nicht, also ist ein Wechseltag erlaubt.
do $$ begin
  alter table public.bookings add constraint one_stamm_at_a_time
    exclude using gist (daterange(arrive, depart, '[)') with &&, stamm with <>)
    where (status in ('confirmed', 'pending'));
exception when duplicate_object or duplicate_table then null; end $$;

create index if not exists bookings_arrive on public.bookings (arrive);

-- Seit 4.1: Hochsaison-Kennzeichen und einzelne Freigaben [{ "by": "uli", "at": "…" }]
alter table public.bookings add column if not exists high_season boolean not null default false;
alter table public.bookings add column if not exists approvals jsonb not null default '[]'::jsonb;

-- ---------------------------------------------------------------------
-- Hochsaison: 1.7.–31.8., erweitert um die Sommerferien in NRW, Hessen, Hamburg
-- (erster bis letzter Ferientag). Jahre ohne Eintrag: nur Juli und August.
-- Muss zu FERIEN in index.html passen – neue Jahre in beiden ergänzen.
-- ---------------------------------------------------------------------
create table if not exists public.high_season (
  year   int primary key,
  starts date not null,
  ends   date not null,
  check (ends >= starts)
);
alter table public.high_season enable row level security;
insert into public.high_season (year, starts, ends) values
  (2026, '2026-06-29', '2026-09-01'),   -- Hessen ab 29.6., NRW bis 1.9.
  (2027, '2027-06-28', '2027-08-31'),   -- Hessen ab 28.6., NRW bis 31.8.
  (2028, '2028-07-01', '2028-08-31')    -- alle Sommerferien (HE/HH 3.7.–11.8., NRW 10.7.–22.8.) liegen in Juli/August
on conflict (year) do update set starts = excluded.starts, ends = excluded.ends;

-- ---------------------------------------------------------------------
-- Hilfsfunktionen
-- ---------------------------------------------------------------------
create or replace function public.berlin_today() returns date
language sql stable set search_path = public as $$
  select (now() at time zone 'Europe/Berlin')::date
$$;

-- Die angemeldete Person (über die E-Mail im Login-Token).
create or replace function public.current_person() returns public.people
language sql stable security definer set search_path = public as $$
  select * from public.people where email = lower(auth.jwt() ->> 'email') limit 1
$$;

create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.people where email = lower(auth.jwt() ->> 'email'))
$$;

create or replace function public.high_season_range(y int) returns daterange
language sql stable security definer set search_path = public as $$
  select coalesce((select daterange(starts, ends, '[]') from public.high_season where year = y),
                  daterange(make_date(y, 7, 1), make_date(y, 8, 31), '[]'))
$$;

-- Mindestens eine Nacht des Aufenthalts liegt in der Hochsaison (Abreisetag zählt nicht).
create or replace function public.touches_high_season(p_arrive date, p_depart date) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from generate_series(extract(year from p_arrive)::int, extract(year from p_depart - 1)::int) y
     where public.high_season_range(y) && daterange(p_arrive, p_depart, '[)'))
$$;

-- Offene Anfragen nach 21 Tagen oder nach verstrichener Anreise verfallen lassen.
create or replace function public.expire_pending() returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  update public.bookings
     set status = 'expired', decided_at = least(now(), created_at + interval '21 days')
   where status = 'pending'
     and (created_at + interval '21 days' < now() or arrive < public.berlin_today());
  get diagnostics n = row_count;
  return n;
end $$;

-- ---------------------------------------------------------------------
-- Aktionen der App (einziger Schreibweg)
-- ---------------------------------------------------------------------
create or replace function public.whoami() returns text
language sql stable security definer set search_path = public as $$
  select id from public.current_person()
$$;

create or replace function public.create_booking(
  p_arrive date, p_depart date, p_companions text[] default '{}', p_guests int default 0, p_note text default ''
) returns public.bookings
language plpgsql security definer set search_path = public as $$
declare
  me public.people;
  clash record;
  comp text[];
  result public.bookings;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.' using errcode = 'P0001'; end if;
  perform public.expire_pending();

  if p_arrive is null or p_depart is null then raise exception 'Wähle Anreise und Abreise.'; end if;
  if p_depart <= p_arrive then raise exception 'Die Abreise muss nach der Anreise liegen.'; end if;
  if p_arrive < public.berlin_today() then raise exception 'Die Anreise liegt in der Vergangenheit.'; end if;
  if p_depart - p_arrive > 31 then raise exception 'Ein Aufenthalt kann höchstens 31 Nächte lang sein.'; end if;
  if coalesce(p_guests, 0) not between 0 and 12 then raise exception 'Höchstens 12 Gäste.'; end if;

  -- Mitreisende: nur Personen aus dem eigenen Stamm, ohne die buchende Person, ohne Doppelte.
  select coalesce(array_agg(distinct c), '{}') into comp
    from unnest(coalesce(p_companions, '{}')) c where c <> me.id;
  if exists (select 1 from unnest(comp) c where not exists
             (select 1 from public.people p where p.id = c and p.stamm = me.stamm)) then
    raise exception 'Mitreisende müssen aus deiner Familie sein.';
  end if;

  select b.arrive, b.depart, p.name into clash
    from public.bookings b join public.people p on p.id = b.booked_by
   where b.status in ('confirmed', 'pending') and b.stamm <> me.stamm
     and daterange(b.arrive, b.depart, '[)') && daterange(p_arrive, p_depart, '[)')
   order by b.arrive limit 1;
  if found then
    raise exception 'Überschneidet sich mit %, %–%. Das Haus ist pro Zeitraum für eine Familie reserviert.',
      clash.name, to_char(clash.arrive, 'DD.MM.'), to_char(clash.depart, 'DD.MM.YYYY');
  end if;

  insert into public.bookings (stamm, booked_by, companions, guests, note, arrive, depart, status, decided_at, high_season)
  values (me.stamm, me.id, comp, coalesce(p_guests, 0), left(trim(coalesce(p_note, '')), 500), p_arrive, p_depart,
          case when me.is_super then 'confirmed' else 'pending' end,
          case when me.is_super then now() end,
          public.touches_high_season(p_arrive, p_depart))
  returning * into result;
  return result;
exception
  when exclusion_violation then
    raise exception 'Gerade hat jemand aus einer anderen Familie diesen Zeitraum gebucht. Bitte neu laden.';
end $$;

create or replace function public.decide_booking(p_id uuid, p_verdict text, p_reason text default '')
returns public.bookings
language plpgsql security definer set search_path = public as $$
declare
  me public.people;
  b public.bookings;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  perform public.expire_pending();

  select * into b from public.bookings where id = p_id for update;   -- sperrt die Zeile: erste Entscheidung gilt
  if not found then raise exception 'Anfrage nicht gefunden.'; end if;
  if b.status <> 'pending' then
    raise exception 'Über diese Anfrage ist schon entschieden (%).',
      case b.status when 'confirmed' then 'freigegeben' when 'rejected' then 'abgelehnt'
                    when 'expired' then 'verfallen' else 'storniert' end;
  end if;

  if b.approvals @> jsonb_build_array(jsonb_build_object('by', me.id)) then
    raise exception 'Du hast schon freigegeben.';
  end if;

  if p_verdict = 'approve' then
    if not me.is_super then
      raise exception 'Freigeben können nur Super-User.';
    end if;
    if not b.high_season and me.stamm = b.stamm then
      raise exception 'Freigeben kann nur ein Super-User aus einer anderen Familie.';
    end if;
    b.approvals := b.approvals || jsonb_build_array(jsonb_build_object('by', me.id, 'at', now()));
    if b.high_season and exists (
         select 1 from public.people p
          where p.is_super and not (b.approvals @> jsonb_build_array(jsonb_build_object('by', p.id))))
    then
      -- Hochsaison: Freigabe gespeichert, es fehlen noch andere
      update public.bookings set approvals = b.approvals where id = p_id returning * into b;
    else
      update public.bookings set approvals = b.approvals, status = 'confirmed', decided_by = me.id, decided_at = now()
       where id = p_id returning * into b;
    end if;
  elsif p_verdict = 'reject' then
    if not me.is_super then raise exception 'Ablehnen können nur Super-User.'; end if;
    if length(trim(coalesce(p_reason, ''))) < 3 then raise exception 'Ohne Begründung ist keine Ablehnung möglich.'; end if;
    update public.bookings set status = 'rejected', decided_by = me.id, decided_at = now(), reason = left(trim(p_reason), 500)
     where id = p_id returning * into b;
  else
    raise exception 'Unbekannte Entscheidung.';
  end if;
  return b;
end $$;

create or replace function public.cancel_booking(p_id uuid) returns public.bookings
language plpgsql security definer set search_path = public as $$
declare
  me public.people;
  b public.bookings;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  select * into b from public.bookings where id = p_id for update;
  if not found then raise exception 'Aufenthalt nicht gefunden.'; end if;
  if b.status not in ('confirmed', 'pending') or b.depart <= public.berlin_today()
     or not (b.booked_by = me.id or (me.is_super and me.stamm = b.stamm)) then
    raise exception 'Stornieren nicht möglich.';
  end if;
  update public.bookings set status = 'cancelled', decided_by = me.id, decided_at = now()
   where id = p_id returning * into b;
  return b;
end $$;

-- Für die tägliche GitHub-Action, damit das kostenlose Projekt nicht pausiert.
create or replace function public.ping() returns timestamptz
language sql stable as $$ select now() $$;

-- ---------------------------------------------------------------------
-- Zugriffsrechte
-- ---------------------------------------------------------------------
alter table public.people   enable row level security;
alter table public.bookings enable row level security;

drop policy if exists "Familie liest Personen" on public.people;
create policy "Familie liest Personen" on public.people
  for select to authenticated using (public.is_member());

drop policy if exists "Familie liest Buchungen" on public.bookings;
create policy "Familie liest Buchungen" on public.bookings
  for select to authenticated using (public.is_member());

-- Projekt ist mit "Automatically expose new tables = aus" angelegt: alle Rechte hier ausdrücklich.
grant usage on schema public to anon, authenticated, service_role;
-- Wöchentliche Sicherung (GitHub Action mit Secret Key = Rolle service_role) darf alles lesen, nichts schreiben.
grant select on public.people, public.bookings, public.high_season to service_role;

-- Kein direktes Schreiben: nur über die Funktionen oben.
revoke all on public.people, public.bookings from anon, authenticated;
grant select (id, name, stamm, is_super, sort) on public.people to authenticated;   -- E-Mails bleiben verborgen
grant select on public.bookings to authenticated;

revoke execute on function public.whoami(), public.create_booking(date, date, text[], int, text),
  public.decide_booking(uuid, text, text), public.cancel_booking(uuid), public.is_member(),
  public.current_person(), public.berlin_today(), public.expire_pending(),
  public.high_season_range(int), public.touches_high_season(date, date) from public, anon, authenticated;
grant execute on function public.whoami(), public.create_booking(date, date, text[], int, text),
  public.decide_booking(uuid, text, text), public.cancel_booking(uuid), public.is_member(),
  public.current_person(), public.berlin_today() to authenticated;
grant execute on function public.ping() to anon, authenticated;

-- ---------------------------------------------------------------------
-- Anmelden dürfen nur E-Mail-Adressen aus "people"
-- ---------------------------------------------------------------------
create or replace function public.guard_signup() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.people where email = lower(new.email)) then
    raise exception 'Diese E-Mail-Adresse ist für Casa la Paz nicht freigeschaltet.';
  end if;
  return new;
end $$;
revoke execute on function public.guard_signup() from public, anon, authenticated;

drop trigger if exists casa_guard_signup on auth.users;
create trigger casa_guard_signup before insert on auth.users
  for each row execute function public.guard_signup();

-- ---------------------------------------------------------------------
-- Familie (danach im Table Editor > people nur noch die E-Mails eintragen)
-- ---------------------------------------------------------------------
insert into public.people (id, name, stamm, is_super, sort) values
  ('micha',   'Micha',   'micha', true,  10),
  ('martina', 'Martina', 'micha', false, 11),   -- nur Mitreisende (ohne E-Mail = kein Login)
  ('leon',    'Leon',    'micha', false, 12),
  ('marilen', 'Marilen', 'micha', false, 13),
  ('olivia',  'Olivia',  'micha', false, 14),
  ('uli',     'Uli',     'uli',   true,  20),
  ('svantje', 'Svantje', 'uli',   false, 21),   -- nur Mitreisende
  ('kaspar',  'Kaspar',  'uli',   false, 22),
  ('karlina', 'Karlina', 'uli',   false, 23),
  ('kajus',   'Kajus',   'uli',   false, 24),
  ('fanny',   'Fanny',   'fanny', true,  30),
  ('kay',     'Kay',     'fanny', false, 31),   -- nur Mitreisende
  ('merle',   'Merle',   'fanny', false, 32)
on conflict (id) do nothing;
