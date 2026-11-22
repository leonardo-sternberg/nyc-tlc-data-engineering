-- Company dimension: one row per High Volume FHV license (the company behind the trip).
-- The list is small and fixed (published by the TLC), so it is written here instead of read
-- from the trips: a `select distinct` over stg_fhvhv_trips would scan 483M rows (~4 GB) for 2 values.
-- Juno and Via are no longer active but are kept, so the codes are documented in one place.

select license_number, company
from unnest([
    struct('HV0002' as license_number, 'Juno' as company),
    struct('HV0003', 'Uber'),
    struct('HV0004', 'Via'),
    struct('HV0005', 'Lyft')
])
