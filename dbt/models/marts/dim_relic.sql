-- Grain: one row per relic. relic_name comes from the game's own localization
-- (relic_catalog seed), falling back to a label derived from the ID.
select
    r.relic_id,
    coalesce(cat.relic_name, {{ readable_id('r.relic_id') }}) as relic_name,
    r.first_seen_run_id,
    r.first_seen_date
from {{ ref('stg_sts2__relics') }} r
left join {{ ref('relic_catalog') }} cat using (relic_id)
