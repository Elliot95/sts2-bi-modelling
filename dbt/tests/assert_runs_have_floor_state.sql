-- Every run should have floor-state rows. Runs abandoned within the first
-- minute legitimately have none (seen in practice: abandoned after 2-3s), so
-- they're excluded; anything else missing floors is a loader problem.
select r.run_id, r.was_abandoned, r.run_time_seconds
from {{ ref('dim_run') }} r
left join {{ ref('fct_floor_state') }} f using (run_id)
where f.run_id is null
  and not (coalesce(r.was_abandoned, false) and r.run_time_seconds < 60)
