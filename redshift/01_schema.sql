-- Redshift Serverless schema + external schema over the gold S3 prefix.
--
-- Deployed via `aws redshift-data execute-statement` (SQL migration
-- pattern) or run from a Redshift Query Editor v2 session.

CREATE SCHEMA IF NOT EXISTS gold_marts;

-- External schema points at the Glue Data Catalog for Spectrum.
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum_gold
    FROM DATA CATALOG
    DATABASE 'ecom_gold'
    IAM_ROLE '${REDSHIFT_IAM_ROLE_ARN}'
    CREATE EXTERNAL DATABASE IF NOT EXISTS;
