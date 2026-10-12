-- One row per choice made in an event or Ancient room. Parses the game's
-- localization key into its parts:
--   events table: BYRDONIS_NEST.pages.INITIAL.options.TAKE -> page INITIAL, option TAKE
--   relics table (Ancients): SEA_GLASS.REGENT -> relic RELIC.SEA_GLASS
select
    cast(run_id as int64)           as run_id,
    cast(run_date as date)          as run_date,
    cast(floor_number as int64)     as floor_number,
    cast(act_index as int64)        as act_index,
    cast(player_id as int64)        as player_id,
    cast(choice_index as int64)     as choice_index,
    event_id,
    choice_table,
    choice_key,
    if(choice_table = 'events', regexp_extract(choice_key, r'\.pages\.([^.]+)\.options\.'), null)  as option_page,
    if(choice_table = 'events', regexp_extract(choice_key, r'\.options\.([^.]+)$'), null)          as option_code,
    if(choice_table = 'relics', concat('RELIC.', split(choice_key, '.')[offset(0)]), null)         as relic_id,
    variables_json
from {{ source('sts2', 'fact_event_choice') }}
