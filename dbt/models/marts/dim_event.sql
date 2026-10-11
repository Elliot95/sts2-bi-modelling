-- Grain: one row per event (including Ancients such as Neow) seen in runs.
-- Names and opening text come from the game's own localization
-- (event_catalog seed); events missing from it keep a derived name.
with seen as (
    select distinct event_id from {{ ref('stg_sts2__event_choices') }}
)

select
    s.event_id,
    coalesce(c.event_name, {{ readable_id('s.event_id') }})    as event_name,
    coalesce(c.event_kind, 'Event')                             as event_kind,
    c.description,
    c.event_id is not null                                      as in_catalog
from seen s
left join {{ ref('event_catalog') }} c using (event_id)
