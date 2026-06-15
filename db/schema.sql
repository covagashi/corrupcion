-- D1 schema. Tables hold precomputed contract rows + irregularity metrics.
-- The Worker only reads from here; all computation happens in pipeline/transform.py.
-- Apply with: npx wrangler d1 execute corrupcion-db --file=db/schema.sql

DROP TABLE IF EXISTS contracts;
CREATE TABLE contracts (
  id                          TEXT PRIMARY KEY, -- ContractID (source-prefixed if needed)
  source                      TEXT NOT NULL,    -- 'flood_control' | 'philgeps' | 'dpwh'
  project_id                  TEXT,
  description                 TEXT,
  type_of_work                TEXT,
  infra_type                  TEXT,
  contractor                  TEXT,
  -- location / political alignment
  region                      TEXT,
  province                    TEXT,
  municipality                TEXT,
  legislative_district        TEXT,
  district_engineering_office TEXT,
  implementing_office         TEXT,
  latitude                    REAL,
  longitude                   REAL,
  -- money
  abc                         REAL,    -- Approved Budget for the Contract (legal ceiling)
  contract_cost               REAL,    -- awarded amount
  infra_year                  INTEGER,
  funding_year                INTEGER,
  completion_year             INTEGER,
  start_date                  INTEGER, -- epoch ms
  -- computed metric (see pipeline/transform.py)
  bid_to_ceiling_ratio        REAL,    -- contract_cost / abc
  risk_flags                  TEXT,    -- JSON array of flag codes, e.g. ["NEAR_CEILING"]
  risk_score                  INTEGER  -- 0-100, higher = more suspicious
);

CREATE INDEX idx_contracts_contractor ON contracts (contractor);
CREATE INDEX idx_contracts_district   ON contracts (legislative_district);
CREATE INDEX idx_contracts_risk       ON contracts (risk_score DESC);

-- Supplier concentration per legislative district (precomputed aggregate).
DROP TABLE IF EXISTS contractor_district_stats;
CREATE TABLE contractor_district_stats (
  contractor           TEXT NOT NULL,
  legislative_district TEXT NOT NULL,
  contract_count       INTEGER NOT NULL,
  total_value          REAL NOT NULL,
  district_value_share REAL NOT NULL, -- this contractor's share of the district's total value (0-1)
  PRIMARY KEY (contractor, legislative_district)
);
