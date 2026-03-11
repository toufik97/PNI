# Series Policy Redesign Spec

## Purpose

This document defines the target redesign for the vaccine policy engine so the app can support:

- clinically correct validation
- deterministic scheduling
- multi-product series such as Pneumo
- availability-aware recommendation
- cross-series timing constraints
- explainable outcomes for every validation and recommendation decision

The redesign replaces the current split between standalone vaccine schedules and vaccine groups with a single policy model centered on clinical series and concrete products.

## Current-State Diagnosis

### What should be preserved

- The current engine flow is directionally good:
  - validate history
  - evaluate grouped vaccines first
  - evaluate standalone vaccines
  - resolve due, upcoming, and next appointment
- The DTP family logic is clinically expressive and already models age- and prior-dose-based product switching.
- The app already tracks invalidation reasons and human-readable notes, which is a strong base for future explainability.

### What must be fixed

- Grouped products can still drift into standalone validation paths, which creates logical overlap.
- The current model assumes one vaccine owns one dose sequence, which cannot represent one clinical series with multiple brands and different brand-specific schedules.
- Group recommendation currently falls back to `ScheduleRule` metadata in the engine, which mixes two policy domains and creates ambiguity.
- There is no native way to model:
  - product brand or manufacturer as first-class policy
  - availability-aware selection
  - cross-series timing dependencies such as `Pneumo >= 15 days after DTP`

## Core Conceptual Shift

The redesign should be modeled around:

- `Series`: the clinical protection track
- `Product`: the actual administered vaccine or brand

Examples:

- `DTP Family` is a `Series`
- `Penta`, `DTC`, and `Td` are `Products`
- `Pneumo` is a `Series`
- `Prevenar13` and `Primovax` are `Products`

This means:

- every administered dose belongs to exactly one clinical series
- every historical dose is validated only through its series policy plus global constraints
- recommendation chooses among allowed products inside the series, not by competing between standalone and grouped logic

## Target Domain Model

### 1. Product

Represents the concrete vaccine item actually administered.

Suggested fields:

- `code`
- `name`
- `manufacturer`
- `is_live`
- `default_dose_amount`
- `description`
- optional antigen tags

Examples:

- `PENTA`
- `DTC`
- `TD`
- `PREVENAR13`
- `PRIMOVAX`

### 2. Series

Represents the clinical protection series.

Suggested fields:

- `code`
- `name`
- `series_type`
- `completion_rule`
- `mixing_policy`
- `selection_policy`
- `description`
- `active`

Examples:

- `DTP_FAMILY`
- `PNEUMO`
- `BCG`
- `RR`

### 3. Series Slot Rule

Defines what the next valid slot in a series requires.

Suggested fields:

- `series`
- `slot_number`
- `prior_valid_series_doses`
- `min_age_days`
- `recommended_age_days`
- `overdue_age_days`
- `max_age_days`
- `min_interval_days`
- `allowed_products`
- `preferred_products`
- `notes`

Design rule:

- slot rules are the only source of truth for series progression
- no fallback into another rule system for target-date or validity calculations

### 4. Series Transition Rule

Controls whether product switching is allowed inside a series.

Suggested use cases:

- require staying on the same product once started
- allow switching only if the original product is unavailable
- allow unrestricted switching
- allow switching only from specific slots onward

### 5. Dependency Rule

Represents cross-series timing constraints.

Example:

- `PNEUMO` requires at least `15` days after the last valid `DTP_FAMILY` dose

Suggested fields:

- `dependent_series`
- `anchor_series`
- `anchor_event`
- `min_offset_days`
- `hard_block`
- `message_template`

### 6. Global Constraint Rule

Represents rules that apply across all series.

Examples:

- live-live 28-day spacing
- substitution conflicts
- incompatible concurrent products

### 7. Inventory Availability

Represents runtime availability, not clinical policy.

Suggested behavior:

- used only when choosing which valid product to recommend now
- must never invalidate historical records

### 8. Policy Version

Every evaluation should reference a policy version so rule changes remain auditable over time.

## Validation and Recommendation Invariants

These should be treated as hard design rules:

- A given administered dose is validated by exactly one series policy.
- Availability affects recommendation only, never retroactive validity.
- Product mixing must be explicit through transition rules.
- Global constraints are orthogonal and applied after local series validation.
- The engine must be deterministic: same child history + same policy version + same availability snapshot = same result.
- No implicit fallback across policy domains is allowed.

## Deterministic Execution Pipeline

### Phase 1: Normalize history

- sort all records by administration date
- compute `age_at_dose_days` once
- map each record from product to its series
- attach normalized metadata needed by validation

### Phase 2: Validate history by series

- group normalized records by series
- validate each series slot-by-slot
- apply:
  - age floor and ceiling
  - interval floor
  - expected product rule
  - transition rule
- build:
  - valid series history
  - invalid records with provenance

### Phase 3: Apply cross-cutting constraints

- apply global live/live and other orthogonal safety rules
- apply dependency rule checks where relevant

### Phase 4: Compute recommendations

For each series:

- identify the next slot
- compute the earliest clinically valid date
- apply dependency rules
- filter allowed products by transition rules
- filter remaining products by availability
- resolve the final recommendation deterministically

### Phase 5: Return explainable outputs

Return:

- `due_today`
- `due_but_unavailable`
- `missing_doses`
- `upcoming`
- `next_appointment`
- `invalid_history`

## Pneumo Design Under the New Model

`Pneumo` should be modeled as one `Series` with two `Products`:

- `Prevenar13`
- `Primovax`

Clinical requirements:

- both products protect the same pneumococcal series
- each product may have its own slot timing
- recommendation should consider availability
- the series must respect a dependency rule of `15 days after DTP Family`

Expected behavior:

- if a child starts `Prevenar13`, the engine follows the `Prevenar13` path unless transition rules permit switching
- if a child starts `Primovax`, the engine follows the `Primovax` path unless transition rules permit switching
- if multiple products are valid and available at a slot, policy decides the preferred product
- if a dose is clinically due but no valid product is available, return `due_but_unavailable`

## DTP End-State

At end-state:

- `DTP Family` is a series
- `Penta`, `DTC`, and `Td` are products inside that series
- DTP progression is modeled entirely by slot rules and transition rules
- standalone DTC schedule length no longer acts as a hidden limiter
- validation and recommendation stay inside the DTP series domain

This removes the current drift where grouped products can still be interpreted through standalone schedule logic.

## Output Contract

Every validation or recommendation result should carry provenance.

Suggested fields:

- `series_code`
- `product_code`
- `slot_number`
- `decision_type`
- `decision_source`
- `rule_key`
- `policy_version`
- `reason_code`
- `message`
- `blocking_constraints`

Recommended decision types:

- `due_today`
- `due_but_unavailable`
- `upcoming`
- `missing`
- `invalid_history`

## Suggested Module Boundaries

### `vaccines/policy_loader.py`

- loads policy from database or serialized policy sources
- constructs normalized in-memory policy objects

### `vaccines/policy_models.py`

- series policy models
- product policy models
- slot rule primitives
- transition rule primitives
- dependency rule primitives

### `vaccines/history_normalizer.py`

- record sorting
- age-at-dose calculation
- product-to-series mapping

### `vaccines/series_validator.py`

- series-local validation only
- no global rule math here

### `vaccines/recommender.py`

- next-slot resolution
- target date calculation
- product selection

### `vaccines/dependencies.py`

- cross-series timing constraints

### `vaccines/global_constraints.py`

- live/live and other orthogonal rule evaluation

### `vaccines/availability.py`

- inventory snapshot handling
- deterministic filtering helpers

### `vaccines/engine.py`

- orchestration only
- no heavy clinical rule math inline

## Vaccine Settings UI Redesign

The current settings UI reflects the old split between vaccines and groups:

- vaccines own schedules
- groups act as a second layer for product switching

That mental model must be replaced.

### New settings information architecture

Recommended tabs:

- `Products`
- `Series`
- `Dependencies`
- `Global Constraints`
- `Guide`

### Products tab

Purpose:

- create and manage concrete products

Fields:

- name
- manufacturer
- live or inactivated
- default dose amount
- description
- optional antigen tags

Example entries:

- `Penta`
- `DTC`
- `Td`
- `Prevenar13`
- `Primovax`

### Series tab

Purpose:

- define the clinical protection series
- configure slot rules and product selection behavior

Fields:

- series name and code
- completion rule
- mixing policy
- selection policy
- active products

Slot editor requirements:

- slot number
- prior valid doses
- min age
- recommended age
- overdue age
- max age
- min interval
- allowed products
- preferred products
- notes

UX requirements:

- show a timeline or slot-based progression view
- support multi-select chips for allowed products
- surface overlap and unreachable-rule errors immediately

### Dependencies tab

Purpose:

- manage cross-series rules

Examples:

- `Pneumo must be at least 15 days after DTP Family`

UX requirements:

- human-readable sentence builder
- clear indication of hard block vs advisory rule

### Global Constraints tab

Purpose:

- manage orthogonal rules such as live/live spacing

Examples:

- 28-day live vaccine spacing
- explicit compatibility exceptions

### Guide tab

Purpose:

- teach admins the new workflow

New setup flow:

1. Create products.
2. Create a clinical series.
3. Add slot rules.
4. Add transition rules if product switching is controlled.
5. Add dependency rules.
6. Review global constraints.

The guide should no longer instruct admins to create both a standalone schedule and a group rule set for the same protection track.

## Admin UX Principles

The settings UI should optimize for correctness, not just CRUD completeness.

Required behaviors:

- proactive validation of overlapping slot windows
- proactive validation of impossible product transitions
- proactive validation of dependency deadlocks
- visible badges for:
  - live
  - dependency-aware
  - multi-product
  - mixing allowed
  - availability-aware
- explainable previews of the rule path for common example children

Recommended enhancement:

- an optional policy simulator panel where an admin can test a child age, prior series doses, and availability snapshot before saving

## Migration Strategy

### Phase 0: Freeze current behavior

- preserve current DTP behavior with regression tests
- use existing DTP tests as baseline

### Phase 1: Introduce new policy concepts

- add `Product`, `Series`, and new rule models
- keep current engine behavior intact initially

### Phase 2: Validator segregation

- stop grouped products from being validated through standalone schedule logic
- separate series-local validation from global constraint checks

### Phase 3: Recommendation extraction

- move recommendation logic into dedicated services
- keep current response shape compatible where possible

### Phase 4: DTP migration

- migrate DTP family into the new series model
- prove parity with current clinically expected outcomes

### Phase 5: Pneumo implementation

- add Pneumo as the first multi-product, availability-aware series
- add `15 days after DTP` dependency rule

### Phase 6: UI migration

- make old schedule/group configuration read-only
- expose new `Products`, `Series`, and `Dependencies` configuration flow

### Phase 7: Provenance and observability

- include rule provenance in all decisions
- add optional evaluation trace for debugging

## Testing Strategy

### Keep existing behavior tests

- preserve current DTP tests as baseline regression protection

### Add validator segregation tests

- grouped or series-bound products must never be validated by standalone rule lookups

### Add series integrity tests

- mixed DTP product histories validate correctly through series slot semantics
- series completion is computed at series level, not product level

### Add Pneumo tests

- Prevenar13 path validates correctly
- Primovax path validates correctly
- switching behavior follows transition policy
- availability influences recommendation, not history validity
- dependency on DTP plus 15 days is enforced

### Add provenance contract tests

- every due, missing, upcoming, and invalid output includes rule provenance

### Add global constraint tests

- live/live spacing remains independent of the underlying series structure

## Non-Negotiable Design Principles

- single source of truth per clinical event
- no hidden fallback across domains
- explicit product switching rules
- deterministic rule selection
- explainable outcomes
- versioned policy evaluation
- backward-compatible migration wherever feasible

## Recommended Implementation Order

1. Build the new policy models.
2. Build history normalization.
3. Extract series-local validation.
4. Add dependency and global-constraint layers.
5. Move recommendation logic into dedicated modules.
6. Migrate DTP first.
7. Add Pneumo second.
8. Replace the settings UI.
9. Remove old cross-domain fallback logic.

## Recommended Reasoning Level For Implementation

Use a high reasoning level for architecture and a medium-high reasoning level for isolated implementation steps.

Recommended working style:

- high reasoning for:
  - data model design
  - migration plan
  - engine pipeline boundaries
  - transition rule semantics
  - dependency rule semantics
- medium-high reasoning for:
  - model coding
  - form and view refactors
  - template updates
  - test authoring
- normal reasoning for:
  - straightforward CRUD wiring
  - list/detail UI rendering
  - mechanical field propagation

Practical recommendation:

- do not implement this in one giant pass
- implement it in small vertical slices with tests at each slice
- start with DTP migration as the first proof that the new architecture is correct
- add Pneumo only after DTP parity is stable

The safest first implementation slice is:

1. introduce `Product` and `Series`
2. map DTP into the new model
3. move DTP validation and recommendation fully into the series layer
4. keep the old UI alive temporarily
5. then build the new settings UI on top of stable policy primitives
