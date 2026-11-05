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
