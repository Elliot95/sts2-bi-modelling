-- run_id is the run's start time in epoch seconds; run_date is derived from it
-- by the loader. A mismatch means the loader's date logic has drifted.
select run_id, run_date
from {{ ref('dim_run') }}
where date(timestamp_seconds(run_id)) != run_date
