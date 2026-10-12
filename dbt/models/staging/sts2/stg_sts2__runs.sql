select
    cast(run_id as int64)               as run_id,
    cast(run_date as date)              as run_date,
    seed,
    build_id,
    game_mode,
    platform_type,
    cast(ascension as int64)            as ascension,
    character,
    cast(acts_completed as int64)       as acts_completed,
    cast(run_time_seconds as int64)     as run_time_seconds,
    killed_by_encounter,
    killed_by_event,
    cast(was_abandoned as bool)         as was_abandoned,
    cast(win as bool)                   as win,
    cast(schema_version as int64)       as schema_version
from {{ source('sts2', 'fact_run') }}
