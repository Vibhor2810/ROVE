-- RØVE migration 002: "Missing a song? Request it". Additive, safe to re-run.
create table if not exists public.rove_song_requests (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  text       text not null check (char_length(text) between 2 and 200),
  language   text,
  created_at timestamptz not null default now()
);
alter table public.rove_song_requests enable row level security;
drop policy if exists "owner member all" on public.rove_song_requests;
create policy "owner member all" on public.rove_song_requests
  for all using (user_id = auth.uid() and public.rove_is_member())
  with check (user_id = auth.uid() and public.rove_is_member());
