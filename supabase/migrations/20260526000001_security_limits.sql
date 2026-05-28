-- Tenant-aware API security counters and queue locks.
-- Used only by the backend service-role client.

CREATE TABLE IF NOT EXISTS public.security_limits (
    key TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('rate', 'lock')),
    count INTEGER NOT NULL DEFAULT 0,
    window_seconds INTEGER,
    expires_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_limits_expires_at
    ON public.security_limits (expires_at);

CREATE OR REPLACE FUNCTION public.security_check_rate_limit(
    p_key TEXT,
    p_window_seconds INTEGER
)
RETURNS TABLE(current_count INTEGER, expires_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_now TIMESTAMPTZ := NOW();
    v_window_start TIMESTAMPTZ;
    v_expires_at TIMESTAMPTZ;
BEGIN
    IF p_key IS NULL OR LENGTH(TRIM(p_key)) = 0 THEN
        RAISE EXCEPTION 'security rate-limit key is required';
    END IF;
    IF p_window_seconds IS NULL OR p_window_seconds <= 0 THEN
        RAISE EXCEPTION 'security rate-limit window must be positive';
    END IF;

    v_window_start := TO_TIMESTAMP(
        FLOOR(EXTRACT(EPOCH FROM v_now) / p_window_seconds) * p_window_seconds
    );
    v_expires_at := v_window_start + MAKE_INTERVAL(secs => p_window_seconds);

    RETURN QUERY
    INSERT INTO public.security_limits AS sl (
        key,
        kind,
        count,
        window_seconds,
        expires_at,
        updated_at
    )
    VALUES (
        p_key,
        'rate',
        1,
        p_window_seconds,
        v_expires_at,
        v_now
    )
    ON CONFLICT (key) DO UPDATE
    SET
        kind = 'rate',
        count = CASE
            WHEN sl.expires_at <= v_now THEN 1
            ELSE sl.count + 1
        END,
        window_seconds = p_window_seconds,
        expires_at = CASE
            WHEN sl.expires_at <= v_now THEN v_expires_at
            ELSE sl.expires_at
        END,
        updated_at = v_now
    RETURNING sl.count, sl.expires_at;
END;
$$;

CREATE OR REPLACE FUNCTION public.security_acquire_lock(
    p_key TEXT,
    p_ttl_seconds INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_now TIMESTAMPTZ := NOW();
    v_expires_at TIMESTAMPTZ;
    v_acquired BOOLEAN := FALSE;
BEGIN
    IF p_key IS NULL OR LENGTH(TRIM(p_key)) = 0 THEN
        RAISE EXCEPTION 'security lock key is required';
    END IF;
    IF p_ttl_seconds IS NULL OR p_ttl_seconds <= 0 THEN
        RAISE EXCEPTION 'security lock ttl must be positive';
    END IF;

    v_expires_at := v_now + MAKE_INTERVAL(secs => p_ttl_seconds);

    WITH upserted AS (
        INSERT INTO public.security_limits AS sl (
            key,
            kind,
            count,
            expires_at,
            updated_at
        )
        VALUES (
            p_key,
            'lock',
            1,
            v_expires_at,
            v_now
        )
        ON CONFLICT (key) DO UPDATE
        SET
            kind = 'lock',
            count = 1,
            expires_at = v_expires_at,
            updated_at = v_now
        WHERE sl.expires_at <= v_now OR sl.kind <> 'lock'
        RETURNING key
    )
    SELECT EXISTS(SELECT 1 FROM upserted) INTO v_acquired;

    RETURN v_acquired;
END;
$$;

CREATE OR REPLACE FUNCTION public.security_release_lock(p_key TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    DELETE FROM public.security_limits
    WHERE key = p_key
      AND kind = 'lock';
END;
$$;
