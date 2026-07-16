-- Glue Data Catalog databases (one per medallion zone).
-- Idempotent: Glue DDL supports IF NOT EXISTS on CREATE DATABASE.

CREATE DATABASE IF NOT EXISTS ecom_bronze
    COMMENT 'Raw envelope-wrapped records from all three ingest paths.'
    LOCATION 's3://${BRONZE_BUCKET}/';

CREATE DATABASE IF NOT EXISTS ecom_silver
    COMMENT 'Cast + dedup + conformed; silver orders are the gold input.'
    LOCATION 's3://${SILVER_BUCKET}/';

CREATE DATABASE IF NOT EXISTS ecom_gold
    COMMENT 'Business marts — fact + aggregate tables for BI consumers.'
    LOCATION 's3://${GOLD_BUCKET}/';
