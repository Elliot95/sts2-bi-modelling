-- One row per rest-site option taken: HEAL, SMITH, or relic-granted options.
select
    cast(run_id as int64)           as run_id,
    cast(run_date as date)          as run_date,
    cast(floor_number as int64)     as floor_number,
    cast(act_index as int64)        as act_index,
    cast(player_id as int64)        as player_id,
    cast(choice_index as int64)     as choice_index,
    rest_option
from {{ source('sts2', 'fact_rest_choice') }}
