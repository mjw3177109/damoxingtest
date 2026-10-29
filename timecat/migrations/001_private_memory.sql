-- TimeCat V2 private long-term memory for a DEDICATED Supabase project.
-- Public schema is accessible to authenticated users ONLY under per-user RLS.
-- This migration NEVER inserts a user's private conversations.
BEGIN;
CREATE TABLE IF NOT EXISTS public.timecat_memory_v2(
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL DEFAULT auth.uid(),
  kind text NOT NULL CHECK (kind IN ('fact','lesson','goal','preference','event','experiment')),
  content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 4000),
  source text NOT NULL CHECK (char_length(source) BETWEEN 1 AND 500),
  status text NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','approved','rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  revision integer NOT NULL DEFAULT 1 CHECK (revision > 0)
);
CREATE INDEX IF NOT EXISTS timecat_memory_v2_owner_updated
    ON public.timecat_memory_v2 (owner_id, updated_at DESC);
ALTER TABLE public.timecat_memory_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timecat_memory_v2 FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.timecat_memory_v2 FROM PUBLIC, anon;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.timecat_memory_v2 TO authenticated;
DROP POLICY IF EXISTS "timecat_owner_select" ON public.timecat_memory_v2;
CREATE POLICY "timecat_owner_select" ON public.timecat_memory_v2 FOR SELECT
TO authenticated USING (owner_id = (SELECT auth.uid()));
DROP POLICY IF EXISTS "timecat_owner_insert" ON public.timecat_memory_v2;
CREATE POLICY "timecat_owner_insert" ON public.timecat_memory_v2 FOR INSERT
TO authenticated WITH CHECK (owner_id = (SELECT auth.uid()));
DROP POLICY IF EXISTS "timecat_owner_update" ON public.timecat_memory_v2;
CREATE POLICY "timecat_owner_update" ON public.timecat_memory_v2 FOR UPDATE
TO authenticated USING (owner_id = (SELECT auth.uid()))
WITH CHECK (owner_id = (SELECT auth.uid()));
DROP POLICY IF EXISTS "timecat_owner_delete" ON public.timecat_memory_v2;
CREATE POLICY "timecat_owner_delete" ON public.timecat_memory_v2 FOR DELETE
TO authenticated USING (owner_id = (SELECT auth.uid()));
COMMIT;
