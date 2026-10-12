-- The raw catalog can contain duplicate card_ids (concurrent loader MERGEs,
-- see docs/gcp_setup.md). Keep the earliest sighting; the strict source test
-- on sts2.dim_card still flags the upstream duplicate.
select
    card_id,
    cast(first_seen_run_id as int64)    as first_seen_run_id,
    cast(first_seen_date as date)       as first_seen_date
from {{ source('sts2', 'dim_card') }}
where card_id is not null
qualify row_number() over (partition by card_id order by first_seen_run_id) = 1
