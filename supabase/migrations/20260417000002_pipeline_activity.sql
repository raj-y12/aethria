-- pipeline_activity: one row per pipeline cycle, tracks what agents did
CREATE TABLE IF NOT EXISTS pipeline_activity (
  id                uuid         DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id           text         NOT NULL,
  timestamp         timestamptz  NOT NULL DEFAULT now(),
  startups_found    int          NOT NULL DEFAULT 0,
  reviewed_count    int          NOT NULL DEFAULT 0,
  decisions_made    int          NOT NULL DEFAULT 0,
  escalations_count int          NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS pipeline_activity_user_ts
  ON pipeline_activity (user_id, timestamp DESC);

-- user_state: tracks last_seen_at per user for activity summary gating
CREATE TABLE IF NOT EXISTS user_state (
  user_id      text        PRIMARY KEY,
  last_seen_at timestamptz NOT NULL DEFAULT now()
);
