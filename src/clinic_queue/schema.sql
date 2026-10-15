-- Clinic queue schema. Safe to run repeatedly (IF NOT EXISTS everywhere).

-- One row per queue day. Exactly one session is open (ended_at IS NULL) at a time.
CREATE TABLE IF NOT EXISTS sessions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at  timestamptz NOT NULL,
    ended_at    timestamptz,
    -- Token counter: bumped with UPDATE ... RETURNING so concurrent issuers queue on the row lock.
    last_number integer NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

-- At most one open session. Indexing a constant makes every open row collide.
CREATE UNIQUE INDEX IF NOT EXISTS sessions_one_open
    ON sessions ((true)) WHERE ended_at IS NULL;

-- One row per patient.
CREATE TABLE IF NOT EXISTS tokens (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  bigint NOT NULL REFERENCES sessions (id),
    number      integer NOT NULL CHECK (number > 0),
    name        text CHECK (char_length(name) BETWEEN 1 AND 60),
    status      text NOT NULL DEFAULT 'waiting'
                CHECK (status IN ('waiting', 'serving', 'done')),
    -- Random id sent with each "Add patient" form; a resent form reuses it (idempotency).
    request_id  uuid NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL,
    called_at   timestamptz,
    finished_at timestamptz,
    UNIQUE (session_id, number)
);

-- At most one patient being served per session.
CREATE UNIQUE INDEX IF NOT EXISTS tokens_one_serving
    ON tokens (session_id) WHERE status = 'serving';
