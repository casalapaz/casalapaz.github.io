-- Casa la Paz 4.3.0: drei Mitreisende ohne eigenes Login + Hochsaison 2028
insert into public.people (id, name, stamm, is_super, sort) values
  ('martina', 'Martina', 'micha', false, 11),
  ('svantje', 'Svantje', 'uli',   false, 21),
  ('kay',     'Kay',     'fanny', false, 31)
on conflict (id) do nothing;

update public.people set sort = case id
  when 'micha' then 10 when 'martina' then 11 when 'leon' then 12 when 'marilen' then 13 when 'olivia' then 14
  when 'uli' then 20 when 'svantje' then 21 when 'kaspar' then 22 when 'karlina' then 23 when 'kajus' then 24
  when 'fanny' then 30 when 'kay' then 31 when 'merle' then 32 else sort end;

insert into public.high_season (year, starts, ends) values (2028, '2028-07-01', '2028-08-31')
on conflict (year) do update set starts = excluded.starts, ends = excluded.ends;
