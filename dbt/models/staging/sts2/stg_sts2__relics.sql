-- Deduped like stg_sts2__cards; the source test flags upstream duplicates.
select
    relic_id,
    cast(first_seen_run_id as int64)    as first_seen_run_id,
    cast(first_seen_date as date)       as first_seen_date
from {{ source('sts2', 'dim_relic') }}
where relic_id is not null
qualify row_number() over (partition by relic_id order by first_seen_run_id) = 1
