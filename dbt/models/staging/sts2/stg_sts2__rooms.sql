-- One row per room on a floor. model_id is the encounter (ENCOUNTER.*) for
-- fights or the event (EVENT.*); monster_ids is pipe-delimited.
select
    cast(run_id as int64)           as run_id,
    cast(run_date as date)          as run_date,
    cast(floor_number as int64)     as floor_number,
    cast(act_index as int64)        as act_index,
    cast(room_index as int64)       as room_index,
    room_type,
    model_id,
    nullif(monster_ids, '')         as monster_ids,
    cast(monster_count as int64)    as monster_count,
    cast(turns_taken as int64)      as turns_taken
from {{ source('sts2', 'fact_room') }}
