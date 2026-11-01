-- Run once in the Supabase SQL Editor. Safe alongside the football tables.
BEGIN;
CREATE TABLE IF NOT EXISTS public.basketball_bets(id text PRIMARY KEY, payload jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS public.basketball_cache(id text PRIMARY KEY, payload jsonb NOT NULL, expires_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS public.basketball_legacy(id text PRIMARY KEY, payload text NOT NULL);
ALTER TABLE public.basketball_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.basketball_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.basketball_legacy ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.basketball_bets, public.basketball_cache, public.basketball_legacy FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.basketball_bets, public.basketball_cache, public.basketball_legacy TO service_role;
COMMIT;
NOTIFY pgrst, 'reload schema';
