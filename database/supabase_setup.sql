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

-- Run once per Supabase project used by the two apps. Safe to repeat.
-- Only adds a separate private log; existing bet/history tables are untouched.
BEGIN;
CREATE TABLE IF NOT EXISTS public.app_prediction_log (
    id text PRIMARY KEY,
    sport text NOT NULL CHECK (sport IN ('football','basketball')),
    captured_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object')
);
ALTER TABLE public.app_prediction_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.app_prediction_log FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT,INSERT ON public.app_prediction_log TO service_role;

CREATE OR REPLACE FUNCTION public.app_list_prediction_logs(p_sport text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path=public
AS $$
    SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY captured_at,id),'[]'::jsonb)
    FROM public.app_prediction_log p WHERE sport=p_sport;
$$;
REVOKE ALL ON FUNCTION public.app_list_prediction_logs(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.app_list_prediction_logs(text) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
