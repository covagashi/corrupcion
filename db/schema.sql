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
  award_date                  INTEGER, -- epoch ms (PhilGEPS award date)
  category                    TEXT,    -- PhilGEPS business_category
  procuring_entity            TEXT,    -- PhilGEPS organization_name
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

-- Threshold-splitting metric, precomputed per complete year (see pipeline/threshold_splitting.py).
DROP TABLE IF EXISTS threshold_splitting_yearly;
CREATE TABLE threshold_splitting_yearly (
  year           INTEGER PRIMARY KEY,
  observed_count INTEGER NOT NULL,
  observed_value REAL    NOT NULL,
  expected_count REAL,            -- NULL when too few bins to fit a tail
  expected_value REAL,
  excess_count   REAL,
  excess_value   REAL,
  minor_total    INTEGER NOT NULL
);

CREATE INDEX idx_contracts_source ON contracts (source);
CREATE INDEX idx_contracts_province ON contracts (province); -- "find your area" browse

-- Legislators directory (Phase 4 — politicians). One row per senator/representative, built
-- offline by pipeline/congress.py from the Open Congress dataset. Note: the source carries NO
-- geographic district, so legislators are NOT joined to contracts by area here.
DROP TABLE IF EXISTS legislators;
CREATE TABLE legislators (
  id              TEXT PRIMARY KEY,
  full_name       TEXT NOT NULL,
  first_name      TEXT,
  last_name       TEXT,
  positions       TEXT,             -- "Senator" | "Representative" | "Senator, Representative"
  is_senator      INTEGER NOT NULL DEFAULT 0,
  is_rep          INTEGER NOT NULL DEFAULT 0,
  congresses      TEXT,             -- JSON array of {number, ordinal, chamber}
  first_congress  INTEGER,
  latest_congress INTEGER,
  aliases         TEXT              -- JSON array of strings
);

CREATE INDEX idx_legislators_name   ON legislators (last_name);
CREATE INDEX idx_legislators_latest ON legislators (latest_congress DESC);

-- Public officials and the offices they held (Phase 4 — alignment). Built offline by
-- pipeline/officials.py from the Open / Raw Philippine Data persons + memberships. This is the
-- dataset that finally carries a geographic key (province / locality) + position + year, so it
-- powers the "who held office in this area" alignment against a contract's province.
DROP TABLE IF EXISTS officials;
CREATE TABLE officials (
  id          TEXT PRIMARY KEY,
  full_name   TEXT NOT NULL,
  first_name  TEXT,
  last_name   TEXT,
  name_suffix TEXT,
  term_count  INTEGER NOT NULL DEFAULT 0,
  latest_year INTEGER,            -- most recent term year, for ordering
  positions   TEXT,               -- JSON: distinct positions ever held
  parties     TEXT                -- JSON: distinct parties
);

CREATE INDEX idx_officials_name ON officials (last_name);

-- One row per (person, office, place, year) membership.
DROP TABLE IF EXISTS official_terms;
CREATE TABLE official_terms (
  id           TEXT PRIMARY KEY,
  person_id    TEXT NOT NULL,
  full_name    TEXT,              -- denormalized so the area join needs no second lookup
  party        TEXT,
  region       TEXT,
  province     TEXT,
  locality     TEXT,
  position     TEXT,
  year         INTEGER,
  province_key TEXT,              -- normalized province (lower/trim) for matching contracts
  locality_key TEXT               -- normalized locality
);

CREATE INDEX idx_terms_person   ON official_terms (person_id);
CREATE INDEX idx_terms_province ON official_terms (province_key);
CREATE INDEX idx_terms_locality ON official_terms (locality_key);

-- PCAB contractor licenses (Phase 4 — owners leg). Built offline by pipeline/pcab.py from the
-- public PCAB /verify/ jqGrid (https://pcabgovph.com/verify/). One row per PCAB-licensed firm;
-- AMO (Authorized Managing Officer) is the disclosed firm owner. contractor_key is the firm name
-- in uppercased alphanumerics-with-spaces form so contracts.contractor can match by string
-- equality after the Worker applies the same transform; owner_surname is the AMO's surname for
-- the surname-overlap alignment with officials/legislators. The Worker only reads the result.
DROP TABLE IF EXISTS pcab_licenses;
CREATE TABLE pcab_licenses (
  id              TEXT PRIMARY KEY,    -- PCAB license id
  license_no      TEXT,
  contractor_name TEXT NOT NULL,
  contractor_key  TEXT NOT NULL,       -- normalized firm name, for matching contracts.contractor
  amo_owner       TEXT,                -- Authorized Managing Officer (disclosed firm owner)
  owner_surname   TEXT,                -- AMO surname (last token), for surname-overlap alignment
  category        TEXT,                -- AAAA / AAA / AA / A / B / C / D / E
  valid_to        TEXT,                -- license validity end date (text, varies in source)
  gov_registered  INTEGER              -- 1 = registered for government infra projects, 0 = no
);

CREATE INDEX idx_pcab_key    ON pcab_licenses (contractor_key);
CREATE INDEX idx_pcab_licno  ON pcab_licenses (license_no);
CREATE INDEX idx_pcab_surname ON pcab_licenses (owner_surname);

-- Contractors with suspended/revoked PCAB licenses — a strong, auditable signal that the firm
-- lost its license to operate, yet may still appear in older (or even newer) awarded contracts.
-- Small table (a few dozen rows). The detail page surfaces a visible "License suspended/revoked"
-- badge when a contract's contractor_key matches a row here.
DROP TABLE IF EXISTS pcab_suspended;
CREATE TABLE pcab_suspended (
  id              TEXT,
  contractor_name TEXT NOT NULL,
  contractor_key  TEXT NOT NULL,
  license_no      TEXT,
  status          TEXT,                -- "License Revoked" / "Suspended" / "Unlicensed Contractor" …
  valid_from      TEXT,
  valid_to        TEXT,
  reason          TEXT,
  PRIMARY KEY (id, status)
);

CREATE INDEX idx_pcabs_key ON pcab_suspended (contractor_key);

-- Political dynasties (Ateneo Policy Center Philippine Political Dynasties Dataset, 2022 Update).
-- Built offline by pipeline/dynasties.py from a local xlsx (the live copy on data.bettergov.ph is
-- 403-blocked from the sandbox). Two tables: politician-level rows (one per source row, with
-- normalized province/locality keys for the join) and the province-year fat-dynasty share that
-- powers the "Dynasty context" panel on the contract detail page. The Worker only reads.
DROP TABLE IF EXISTS dynasty_politicians;
CREATE TABLE dynasty_politicians (
  surname        TEXT,                -- last_name uppercased (for the surname join)
  first_name     TEXT,
  last_name      TEXT,
  party          TEXT,
  region         TEXT,
  province       TEXT,                -- original province name from Ateneo
  province_key   TEXT,                -- normalized province, for matching contracts/officials
  municipality   TEXT,
  locality_key   TEXT,                -- normalized municipality
  position       TEXT,
  year           INTEGER,
  psgc_province  TEXT,                -- PSGC code (e.g. PH04340000), kept for future joins
  is_fat         INTEGER NOT NULL DEFAULT 0  -- 1 = fat political dynasty, 0 = non-fat
);

CREATE INDEX idx_dynpoll_provkey  ON dynasty_politicians (province_key);
CREATE INDEX idx_dynpoll_surname  ON dynasty_politicians (surname, province_key);
CREATE INDEX idx_dynpoll_provfat ON dynasty_politicians (province_key, is_fat);

-- Province-level fat-dynasty share per election year (1992..2022, every 3 years). 81 provinces x
-- ~11 election years. The contract detail page reads the closest available election year to the
-- contract's year and shows the share, plus the province's position vs the national mean.
DROP TABLE IF EXISTS dynasty_shares;
CREATE TABLE dynasty_shares (
  province_key TEXT NOT NULL,
  province     TEXT NOT NULL,
  year         INTEGER NOT NULL,
  share        REAL NOT NULL,        -- fat dynasty share in percent (0..100)
  PRIMARY KEY (province_key, year)
);

CREATE INDEX idx_dynshare_year ON dynasty_shares (year);
