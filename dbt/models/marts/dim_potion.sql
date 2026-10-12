-- Grain: one row per potion seen in runs (offered, used, bought or held).
-- Names and effect text come from the game's localization (potion_catalog
-- seed); potions missing from it keep a derived name.
with seen as (
    select potion_id from {{ ref('stg_sts2__potion_events') }}
    union distinct
    select potion_id from {{ ref('stg_sts2__run_potions') }}
)

select
    s.potion_id,
    coalesce(c.potion_name, {{ readable_id('s.potion_id') }})  as potion_name,
    c.description,
    c.potion_id is not null                                     as in_catalog
from seen s
left join {{ ref('potion_catalog') }} c using (potion_id)
