-- deploy_views.sql
-- Run this in Azure SQL to deploy all staging and mart views in dependency order.
-- Safe to re-run at any time — all views use CREATE OR ALTER.
--
-- Order:
--   1. Schemas
--   2. Staging views   (read from staging tables)
--   3. Mart views      (read from staging views)

-- ── 1. Schemas ────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'staging')
    EXEC('CREATE SCHEMA staging');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'mart')
    EXEC('CREATE SCHEMA mart');
GO

-- ── 2. Staging views ──────────────────────────────────────────────────────
:r sql/staging/v_national_summary.sql
:r sql/staging/v_state_summary.sql
:r sql/staging/v_fulltime_parttime.sql
:r sql/staging/v_industry_employment.sql

-- ── 3. Mart views ─────────────────────────────────────────────────────────
:r sql/mart/v_national_overview.sql
:r sql/mart/v_unemployment_by_state.sql
:r sql/mart/v_industry_breakdown.sql
:r sql/mart/v_fulltime_parttime.sql
