-- Schema do Sistema de Gestão de Incidentes
-- Execute no Supabase: SQL Editor > New Query > cole e rode

-- ─── configurations ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS configurations (
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(100)  NOT NULL UNIQUE,
    value       VARCHAR(500)  NOT NULL,
    description VARCHAR(300)  NOT NULL DEFAULT '',
    category    VARCHAR(100)  NOT NULL DEFAULT 'general',
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_configurations_key ON configurations (key);

-- ─── systems ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS systems (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(300) NOT NULL DEFAULT '',
    criticality VARCHAR(10)  NOT NULL DEFAULT 'media',   -- alta | media | baixa
    active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- ─── incident_types ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incident_types (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(300) NOT NULL DEFAULT '',
    active      BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ─── incidents ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    id                  SERIAL PRIMARY KEY,
    incident_id         VARCHAR(20)  NOT NULL UNIQUE,
    title               VARCHAR(200) NOT NULL,
    description         TEXT         NOT NULL DEFAULT '',

    system_id           INTEGER      NOT NULL REFERENCES systems(id),
    incident_type_id    INTEGER      NOT NULL REFERENCES incident_types(id),

    priority            VARCHAR(5)   NOT NULL,           -- P1 | P2 | P3 | P4
    status              VARCHAR(20)  NOT NULL DEFAULT 'Aberto',  -- Aberto | Em Andamento | Resolvido

    started_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    ended_at            TIMESTAMP WITHOUT TIME ZONE,

    duration_minutes    FLOAT,
    production_loss     FLOAT,
    financial_loss      FLOAT,

    root_cause          TEXT NOT NULL DEFAULT '',
    resolution_notes    TEXT NOT NULL DEFAULT '',
    affected_users      INTEGER NOT NULL DEFAULT 0,

    created_by          VARCHAR(100) NOT NULL DEFAULT 'sistema',
    created_at          TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_incidents_incident_id ON incidents (incident_id);
