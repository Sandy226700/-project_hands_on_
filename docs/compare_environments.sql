-- Run on each environment (Dev, Test, Prod) and compare the results.
-- group_concat_max_len must be raised, otherwise the database cuts the
-- concatenated text off at 1024 characters and the fingerprint is wrong.
SET SESSION group_concat_max_len = 1000000;

SELECT 'stg_csv' AS tbl, COUNT(*) AS n,
  MD5(GROUP_CONCAT(CONCAT_WS('|', transaction_id, account_id, transaction_date, transaction_type, amount, branch_id) ORDER BY transaction_id SEPARATOR ';')) AS fingerprint
FROM stg_csv
UNION ALL
SELECT 'stg_txt', COUNT(*),
  MD5(GROUP_CONCAT(CONCAT_WS('|', transaction_id, account_id, transaction_date, transaction_type, amount, branch_id) ORDER BY transaction_id SEPARATOR ';'))
FROM stg_txt
UNION ALL
SELECT 'stg_json', COUNT(*),
  MD5(GROUP_CONCAT(CONCAT_WS('|', transaction_id, account_id, transaction_date, transaction_type, amount, branch_id) ORDER BY transaction_id SEPARATOR ';'))
FROM stg_json
UNION ALL
SELECT 'stg_xlsx', COUNT(*),
  MD5(GROUP_CONCAT(CONCAT_WS('|', transaction_id, account_id, transaction_date, transaction_type, amount, branch_id) ORDER BY transaction_id SEPARATOR ';'))
FROM stg_xlsx
UNION ALL
SELECT 'stg_pdf', COUNT(*),
  MD5(GROUP_CONCAT(CONCAT_WS('|', transaction_id, account_id, transaction_date, transaction_type, amount, branch_id) ORDER BY transaction_id SEPARATOR ';'))
FROM stg_pdf;
