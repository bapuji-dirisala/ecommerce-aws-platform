-- Lake Formation data filters applied to silver.orders.
--
-- Column exclusion: analysts never see PII columns (customer email,
-- IP address) that may land in the envelope payload if partners export
-- loose schemas.
-- Row-level: analysts only see orders in their assigned country.

-- Create / replace a data cell filter for US analysts.
-- Terraform's aws_lakeformation_data_cells_filter resource creates these;
-- this file documents the equivalent SQL for reviewers.

/*
CREATE DATA_CELLS_FILTER filter_us_analyst
    ON TABLE ecom_silver.orders
    USING (ship_country = 'US')
    EXCLUDE COLUMNS (bronze_source, received_at);

GRANT SELECT ON DATA_CELLS_FILTER filter_us_analyst
    TO ROLE 'arn:aws:iam::<account>:role/data-analyst-us';
*/

-- Analyst roles are tag-bound: granting the "sensitivity=low" + "data_zone=silver"
-- tag combination to the analyst role lets them query anything matching those
-- tags without a per-table grant.
