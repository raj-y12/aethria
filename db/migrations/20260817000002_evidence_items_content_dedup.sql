-- Audit HIGH-B5: evidence_items had no content-based dedup at all -- unlike
-- evidence_artifacts (unique on user_id, content_hash, access_class with
-- "on conflict do nothing"), re-ingesting the same artifact unconditionally
-- inserted a new item row every time, even for byte-identical content.
-- Running the same evidence plan twice (a real, checked scenario -- the
-- backfill script overlapping a live dispatch) created duplicate current
-- claims via duplicate evidence_items, and evaluate_snapshot averages every
-- current claim of a type, so a score could silently drift based on how many
-- times extraction happened to run rather than evidence quality.

alter table public.evidence_items
  add column if not exists content_hash text;

update public.evidence_items
  set content_hash = encode(sha256(convert_to(display_excerpt, 'UTF8')), 'hex')
  where content_hash is null;

alter table public.evidence_items
  alter column content_hash set not null;

-- Pre-existing duplicates (the exact bug this migration fixes) would violate
-- the unique index below. Keep the earliest row per (user_id, artifact_id,
-- content_hash) and drop the rest -- same "oldest wins" rule dedup-on-insert
-- will enforce going forward. Links to the rows being dropped are dropped
-- first (they point at duplicate content, so they're redundant, not lost --
-- the surviving row's links already cover the same claim relationships).
delete from public.claim_evidence_links l
  using public.evidence_items a, public.evidence_items b
  where l.user_id = a.user_id
    and l.evidence_item_id = a.evidence_item_id
    and a.user_id = b.user_id
    and a.artifact_id = b.artifact_id
    and a.content_hash = b.content_hash
    and a.created_at > b.created_at
    and a.evidence_item_id <> b.evidence_item_id;

delete from public.evidence_items a
  using public.evidence_items b
  where a.user_id = b.user_id
    and a.artifact_id = b.artifact_id
    and a.content_hash = b.content_hash
    and a.created_at > b.created_at
    and a.evidence_item_id <> b.evidence_item_id;

create unique index if not exists evidence_items_artifact_content_dedup
  on public.evidence_items (user_id, artifact_id, content_hash);
