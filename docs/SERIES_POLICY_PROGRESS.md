# Series Policy Redesign Progress

Last updated: 2026-03-12

## Current Status

Overall redesign progress is approximately 70 percent complete.

The current implementation checkpoint after the redesign review includes:

- extracted policy-loading into `vaccines/policy_loader.py`
- extracted availability selection into `vaccines/availability.py`
- extracted dependency evaluation into `vaccines/dependencies.py`
- extracted live-vaccine global constraint handling into `vaccines/global_constraints.py`
- refactored `vaccines/engine.py` to delegate to those modules
- extracted series recommendation flow into `vaccines/recommender.py`
- made legacy vaccine and legacy group configuration read-only in the settings UI and views
- expanded module-boundary tests to cover the new service layer
- expanded module-boundary tests to cover the recommender service
- expanded settings UI tests to cover the read-only migration path
- verified the full Django test suite passes

## Completed

- [x] Introduce `Product`, `Series`, `SeriesRule`, `DependencyRule`, and `PolicyVersion`
- [x] Add series-backed validation and recommendation paths
- [x] Add provenance to engine outputs
- [x] Add policy version support
- [x] Add first-slice settings UI for products, series, dependencies, versions, and guide
- [x] Extract policy-loading, dependency, availability, and live global-constraint services from the engine
- [x] Extract series recommendation flow into a dedicated recommender service
- [x] Replace inline engine rule math with dedicated recommender and policy-loader orchestration boundaries
- [x] Make legacy vaccine and legacy group configuration read-only during migration

## In Progress

- [ ] Remove legacy engine fallback for migrated series
- [ ] Finish DTP migration so it no longer depends on legacy group or schedule fallback
- [ ] Expand Pneumo from first-slice support to full end-state multi-product series support

## Remaining Major Work

- [ ] Add explicit transition-rule model and semantics
- [ ] Add global-constraint rule model beyond live/live spacing
- [ ] Add runtime availability snapshot abstraction instead of storing availability only on `Product`

- [ ] Add `Global Constraints` settings tab
- [ ] Add proactive admin validation for overlap, deadlock, and impossible-transition cases
- [ ] Add optional policy simulator UI
- [ ] Remove old cross-domain fallback logic after DTP parity is proven

## Next Recommended Slice

1. Finish DTP parity entirely inside the series domain.
2. Once DTP is isolated, remove group and schedule fallback for the DTP protection track.
3. Add explicit transition-rule modeling for product switching.
4. Add a first end-state `Global Constraints` tab and rule model.



