# Series Policy Redesign Progress

Last updated: 2026-03-12

## Current Status

Overall redesign progress is approximately 93 percent complete.

The current implementation checkpoint after the redesign review includes:

- extracted policy-loading into `vaccines/policy_loader.py`
- extracted availability selection into `vaccines/availability.py`
- extracted dependency evaluation into `vaccines/dependencies.py`
- extracted live-vaccine global constraint handling into `vaccines/global_constraints.py`
- refactored `vaccines/engine.py` to delegate to those modules
- extracted series recommendation flow into `vaccines/recommender.py`
- made legacy vaccine and legacy group configuration read-only in the settings UI and views
- added explicit `SeriesTransitionRule` modeling and migration-backed switching semantics
- exposed transition-rule authoring in the series create/edit UI and series settings summary
- suppressed legacy group fallback when an active series already owns the full legacy group track
- moved the shared DTP policy fixture to explicit series rules instead of deriving them from legacy group and schedule data
- removed the engine's direct reliance on `legacy_group` for suppressing duplicate group fallback
- added proactive transition overlap validation in the series admin flow
- added proactive dependency slot-reference validation for both dependent and anchor series slots
- added `GlobalConstraintRule` modeling plus a Global Constraints settings tab
- wired live/live spacing to read from policy instead of only using a hardcoded default
- expanded module-boundary tests to cover the new service layer
- expanded module-boundary tests to cover the recommender service
- added transition-rule tests for strict, flexible, and unavailable-only switching behavior
- added global-constraint tests for policy-driven live spacing and settings CRUD
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
- [x] Add explicit transition-rule model and semantics
- [x] Expose transition-rule configuration in the series settings UI
- [x] Suppress duplicate legacy group evaluation for series-owned tracks
- [x] Add a first end-state `Global Constraints` tab and rule model

## In Progress

- [ ] Remove legacy engine fallback for migrated series
- [ ] Finish DTP migration in application policy data so production DTP no longer depends on schedule fallback or legacy group metadata outside transitional admin views
- [ ] Expand Pneumo from first-slice support to full end-state multi-product series support

## Remaining Major Work

- [ ] Add runtime availability snapshot abstraction instead of storing availability only on `Product`

- [ ] Expand proactive admin validation beyond transition overlap and direct dependency cycles into broader deadlocks and impossible cross-rule combinations
- [ ] Add optional policy simulator UI
- [ ] Remove old cross-domain fallback logic after DTP parity is proven

## Next Recommended Slice

1. Finish DTP parity entirely inside the series domain.
2. Once DTP is isolated, remove group and schedule fallback for the DTP protection track.
3. Expand Pneumo on top of the transition-rule-aware and availability-aware series path.
4. Add proactive admin validation for overlap, deadlock, and impossible-transition cases.
