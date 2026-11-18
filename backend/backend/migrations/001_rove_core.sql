-- RØVE migration 001: invite-only membership, sets, favourites, play history.
-- ADDITIVE ONLY: creates new rove_* tables and functions. It does not alter,
-- drop or reset your existing tables (profiles, artists, songs, mixtapes,
-- mixtape_tracks, audio_features, favorites). Safe to re-run.
-- Apply in the Supabase SQL editor (or `supabase db push`).

create extension if not exists pgcrypto;

-- ---------- invitations & membership ----------
create table if not exists public.rove_invitations (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique check (char_length(code) >= 8),
  note        text,
  expires_at  timestamptz,
  used_by     uuid references auth.users(id) on delete set null,
  used_at     timestamptz,
  created_at  timestamptz not null default now()
);
alter table public.rove_invitations enable row level security;
-- No policies on purpose: clients can never read or write invitations directly.
-- Only the SECURITY DEFINER functions below touch the table. Create invites as
-- the project owner (SQL editor): insert into rove_invitations(code) values ('...');

create table if not exists public.rove_members (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  invite_id  uuid references public.rove_invitations(id),
  joined_at  timestamptz not null default now()
);
alter table public.rove_members enable row level security;
drop policy if exists "member reads own row" on public.rove_members;
create policy "member reads own row" on public.rove_members
  for select using (user_id = auth.uid());

create or replace function public.rove_is_member()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.rove_members where user_id = auth.uid());
$$;

create or replace function public.rove_validate_invite(p_code text)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.rove_invitations
    where code = p_code and used_by is null
      and (expires_at is null or expires_at > now())
  );
$$;
grant execute on function public.rove_validate_invite(text) to anon, authenticated;

create or replace function public.rove_redeem_invite(p_code text)
returns boolean language plpgsql security definer set search_path = public as $$
declare v_id uuid;
begin
  if auth.uid() is null then return false; end if;
  -- atomic check-and-consume: two people cannot use the same code
  update public.rove_invitations
     set used_by = auth.uid(), used_at = now()
   where code = p_code and used_by is null
     and (expires_at is null or expires_at > now())
  returning id into v_id;
  if v_id is null then return false; end if;
  insert into public.rove_members(user_id, invite_id) values (auth.uid(), v_id)
    on conflict (user_id) do nothing;
  return true;
end $$;
grant execute on function public.rove_redeem_invite(text) to authenticated;

-- ---------- saved sets ----------
create table if not exists public.rove_sets (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  name          text not null check (char_length(name) between 1 and 120),
  preferences   jsonb not null default '{}'::jsonb,
  tracks        jsonb not null default '[]'::jsonb,   -- snapshot of provider metadata
  completed     boolean not null default false,
  skipped_count int not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists rove_sets_user_idx on public.rove_sets(user_id, created_at desc);

-- ---------- favourites ----------
create table if not exists public.rove_favorites (
  user_id    uuid not null references auth.users(id) on delete cascade,
  track_id   text not null,
  track      jsonb not null,
  created_at timestamptz not null default now(),
  primary key (user_id, track_id)
);

-- ---------- play history ----------
create table if not exists public.rove_play_history (
  id        bigint generated always as identity primary key,
  user_id   uuid not null references auth.users(id) on delete cascade,
  track_id  text not null,
  track     jsonb not null,
  mode      text not null check (mode in ('segment','full')),
  completed boolean not null default false,
  played_at timestamptz not null default now()
);
create index if not exists rove_history_user_idx on public.rove_play_history(user_id, played_at desc);

create or replace function public.rove_touch_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists rove_sets_touch on public.rove_sets;
create trigger rove_sets_touch before update on public.rove_sets
  for each row execute function public.rove_touch_updated_at();

-- ---------- RLS: owner AND member ----------
do $$
declare t text;
begin
  foreach t in array array['rove_sets','rove_favorites','rove_play_history'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "owner member all" on public.%I', t);
    execute format($p$create policy "owner member all" on public.%I
      for all using (user_id = auth.uid() and public.rove_is_member())
      with check (user_id = auth.uid() and public.rove_is_member())$p$, t);
  end loop;
end $$;
