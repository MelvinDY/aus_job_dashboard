-- 00_schemas.sql
-- Run once to create the staging and mart schemas.
-- Safe to re-run — IF NOT EXISTS guards on both.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'staging')
    EXEC('CREATE SCHEMA staging');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'mart')
    EXEC('CREATE SCHEMA mart');
GO
