-- ---------------------------------------------------------------------
-- Ausgleich (seit 4.7.0): Super-User tragen ein, dass ihre Familie Kosten
-- eines Jahres beglichen hat (wie bei Splitwise, ohne Nachweis, auf Vertrauen).
-- Nichts wird gelöscht: Rücknahmen bleiben mit Name und Zeitpunkt sichtbar.
-- Offener Betrag = Kosten (bestätigte Nächte über 21, 200 € pro Woche) minus
-- Ausgleiche. Beliebig oft ausführbar.
-- ---------------------------------------------------------------------
create table if not exists public.payments (
  id            uuid primary key default gen_random_uuid(),
  stamm         text not null check (stamm in ('micha', 'uli', 'fanny')),
  year          int  not null check (year between 2026 and 2100),
  amount_cents  int  not null check (amount_cents between 1 and 10000000),
  note          text not null default '' check (length(note) <= 140),
  created_by    text not null references public.people (id),
  created_at    timestamptz not null default now(),
  voided_by     text references public.people (id),
  voided_at     timestamptz,
  check ((voided_by is null) = (voided_at is null))
);
create index if not exists payments_stamm_year on public.payments (stamm, year);
alter table public.payments enable row level security;

drop policy if exists "Familie liest Ausgleiche" on public.payments;
create policy "Familie liest Ausgleiche" on public.payments
  for select to authenticated using (public.is_member());

revoke all on public.payments from anon, authenticated;
grant select on public.payments to authenticated;

-- Kosten einer Familie in einem Jahr in Cent (gleiche Rechnung wie in der App).
create or replace function public.family_cost_cents(p_stamm text, p_year int) returns int
language sql stable security definer set search_path = public as $$
  select round(greatest(0, count(distinct d::date) - 21) * 20000.0 / 7)::int
    from public.bookings b, generate_series(b.arrive, b.depart - 1, interval '1 day') d
   where b.stamm = p_stamm and b.status = 'confirmed' and extract(year from d) = p_year
$$;

create or replace function public.family_open_cents(p_stamm text, p_year int) returns int
language sql stable security definer set search_path = public as $$
  select public.family_cost_cents(p_stamm, p_year)
       - coalesce((select sum(amount_cents) from public.payments
                    where stamm = p_stamm and year = p_year and voided_at is null), 0)::int
$$;

create or replace function public.record_payment(p_year int, p_amount_cents int, p_note text default '')
returns public.payments
language plpgsql security definer set search_path = public as $$
declare
  me public.people;
  open_c int;
  result public.payments;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  if not me.is_super then raise exception 'Ausgleichen können nur Super-User.'; end if;
  if p_year is null or p_year < 2026 or p_year > extract(year from public.berlin_today())::int + 2 then
    raise exception 'Für dieses Jahr ist kein Ausgleich möglich.';
  end if;
  if coalesce(p_amount_cents, 0) < 1 then raise exception 'Gib einen Betrag über 0 € ein.'; end if;
  perform pg_advisory_xact_lock(hashtext('casa-payments-' || me.stamm || '-' || p_year));   -- zwei gleichzeitige Einträge
  open_c := public.family_open_cents(me.stamm, p_year);
  if open_c <= 0 then raise exception 'Für % ist nichts offen.', p_year; end if;
  if p_amount_cents > open_c then
    raise exception 'Offen sind nur noch % €.', replace(to_char(open_c / 100.0, 'FM9999990.00'), '.', ',');
  end if;
  insert into public.payments (stamm, year, amount_cents, note, created_by)
  values (me.stamm, p_year, p_amount_cents, left(trim(coalesce(p_note, '')), 140), me.id)
  returning * into result;
  return result;
end $$;

create or replace function public.void_payment(p_id uuid) returns public.payments
language plpgsql security definer set search_path = public as $$
declare
  me public.people;
  p public.payments;
begin
  me := public.current_person();
  if me.id is null then raise exception 'Du bist nicht angemeldet.'; end if;
  select * into p from public.payments where id = p_id for update;
  if not found then raise exception 'Eintrag nicht gefunden.'; end if;
  if not me.is_super or me.stamm <> p.stamm then
    raise exception 'Zurücknehmen kann nur der Super-User der Familie.';
  end if;
  if p.voided_at is not null then raise exception 'Dieser Ausgleich ist schon zurückgenommen.'; end if;
  update public.payments set voided_by = me.id, voided_at = now() where id = p_id returning * into p;
  return p;
end $$;

revoke execute on function public.family_cost_cents(text, int), public.family_open_cents(text, int),
  public.record_payment(int, int, text), public.void_payment(uuid) from public, anon, authenticated;
grant execute on function public.record_payment(int, int, text), public.void_payment(uuid) to authenticated;

do $$ begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (select 1 from pg_publication_tables
                      where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'payments') then
    alter publication supabase_realtime add table public.payments;
  end if;
end $$;
