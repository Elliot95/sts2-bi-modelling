-- Grain: one row per run / floor / player.
select
    run_id,
    floor_number,
    player_id,
    act_index,
    map_point_index,
    map_point_type,
    current_hp,
    max_hp,
    current_gold,
    damage_taken,
    hp_healed,
    gold_gained,
    gold_lost,
    gold_spent,
    gold_stolen,
    max_hp_gained,
    max_hp_lost
from {{ ref('stg_sts2__floor_states') }}
