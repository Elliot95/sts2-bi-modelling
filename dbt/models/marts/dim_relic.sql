-- Grain: one row per relic. relic_name derived from the ID like dim_card.
select
    relic_id,
    {{ readable_id('relic_id') }} as relic_name,
    first_seen_run_id,
    first_seen_date
from {{ ref('stg_sts2__relics') }}
