-- SQLite Latest-State Schema for Southern Vietnamese Lottery (XSMN)
-- Retention Policy: 1 row per province (latest draw only, overwritten on sync).

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS latest_lottery_results (
    province_code TEXT PRIMARY KEY NOT NULL,
    draw_date     TEXT NOT NULL CHECK (draw_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    prizes        TEXT NOT NULL CHECK (json_valid(prizes)),
    updated_at    DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) WITHOUT ROWID;

-- Index on draw_date for fast freshness checks and filtering by latest draw date
CREATE INDEX IF NOT EXISTS idx_latest_lottery_draw_date
    ON latest_lottery_results (draw_date DESC);

