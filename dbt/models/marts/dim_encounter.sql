-- Grain: one row per encounter fought in runs. Name and the game's own death
-- line ("{character} was dismembered by an {encounter}.") come from the
-- encounter_catalog seed. encounter_type comes from the ID suffix; Weak is
-- the easier act-opening pool of normal fights.
with seen as (
    select distinct model_id as encounter_id
    from {{ ref('stg_sts2__rooms') }}
    where room_type in ('monster', 'elite', 'boss') and model_id is not null
)

select
    s.encounter_id,
    coalesce(c.encounter_name, {{ readable_id('s.encounter_id', ['WEAK', 'NORMAL', 'ELITE', 'BOSS']) }}) as encounter_name,
    case
        when ends_with(s.encounter_id, '_BOSS')  then 'Boss'
        when ends_with(s.encounter_id, '_ELITE') then 'Elite'
        when ends_with(s.encounter_id, '_WEAK')  then 'Weak'
        else 'Normal'
    end                                                         as encounter_type,
    c.loss_text
from seen s
left join {{ ref('encounter_catalog') }} c using (encounter_id)
