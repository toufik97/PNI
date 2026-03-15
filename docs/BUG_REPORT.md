# 🐞 Vaccination Engine Bug Report & Logic Gaps

This document tracks identified issues, edge cases, and technical debt in the vaccination engine. Each entry includes a description of the problem and the potential impact.

---

## [BUG-001] Logic Overlap: History Validation vs. Group Protection
**Date Identified:** 2026-03-10
**Component:** `vaccines/engine.py` -> `_validate_history()`

### Description
The engine currently validates historical vaccination records by looking up individual `ScheduleRule` entries for each vaccine. For example, it looks for "DTC Dose 3" to check its safety floor.
However, because the **DTP Family Group** now handles protection logic for children starting late, a child might receive **4 or 5 doses of DTC**. 

Since the individual `DTC` schedule rule only defines 2 doses, the history validator:
1. Cannot find a rule for "DTC Dose 3".
2. Fails to validate the "Safety Floor" (`min_age_days`) for those additional doses.
3. May incorrectly report "Rule not found" instead of checking against the Group Policy.

### Impact
- **Security:** Potential for invalid doses (too early) to be treated as valid if they exceed the individual rule count.
- **Accuracy:** Maintenance of individual rules becomes confusing if they must mirror Group Rules.

### Recommended Fix
Update `_validate_history` to **skip** any vaccine that belongs to a `VaccineGroup`. Create a specialized `_validate_group_history` method that uses the `GroupRule` sequence to validate past doses instead.

**Status**: ✅ Resolved. The entire engine has been refactored (Series Policy Redesign) to evaluate doses primarily via abstract `Series` (e.g., DTP Series) and its `SeriesRule`s rather than looking up individual vaccine `ScheduleRule`s. History validation now uses `SeriesHistoryValidator` which correctly checks the safety floors and validation logic for any number of valid doses that a Series dictates, rendering the "Rule not found" issue obsolete.

---

## [GAP-001] Reporting Ambiguity: Vial vs. Protection
**Date Identified:** 2026-03-10
**Component:** Reporting UI / Data Export

### Description
If a report is generated based on individual vaccine counts (e.g., "Kids with 2 doses of DTC"), it will incorrectly flag "Caught-up" children as complete, even though the **DTP Family** policy requires 5 total doses for the same protection.

### Impact
- **Public Health:** Misleading statistics on population immunity levels.
- **Patient Safety:** Children might be marked as "Fully Vaccinated" when they are actually missing boosters.

### Recommended Fix
All analytics and "Completion" badges in the UI must be calculated at the **Group/Family level**, not at the individual vaccine level.

---

---
 
 ## [BUG-002] Missing Cross-Vaccine Live Interval Validation
 **Date Identified:** 2026-03-10
 **Component:** `vaccines/engine.py` -> `_validate_history()`
 
 ### Description
 The engine correctly prevents **recommending** a live vaccine if another was given recently (< 28 days). However, it fails to **invalidate** a dose if it is manually recorded during that forbidden window. 
 
 For example: A child receiving **BCG** (live) on Monday and **RR** (live) on Tuesday should have the second dose flagged as **Invalid** due to the 28-day live-to-live requirement. Currently, the engine accepts both as valid because they belong to different groups and have no direct interval rules between them.
 
 ### Impact
 - **Patient Safety:** Clinical records incorrectly show a valid dose when its efficacy is compromised by a recent live vaccine.
 - **Compliance:** System is not fully enforcing the global live vaccine policy.
 
 ### Recommended Fix (Resolved)
 Implement a global validation pass in `_validate_history` that extracts all live vaccine records and ensures that any two such records are either given on the **same day** or at least **28 days apart**. Any record violating this must be flagged with `REASON_INTERVAL`.
 
 **Status**: ✅ Resolved (2026-03-10). Implementation added to `engine.py` with support for rule-based compatibility exceptions (e.g., OPV).
 
 ---
 
 *(Add new bugs below this line)*

## [BUG-003] Overlapping Series Recommendations (The "Penta 1 and Penta 2" Contradiction)
**Date Identified:** 2026-03-15
**Component:** `vaccines/engine.py` -> `_normalize_due_items()`

### Description
The engine correctly evaluates each `Series` independently. However, some vaccines (like combination vaccines e.g. **Penta**) satisfy the requirements of multiple series simultaneously. 

Currently, if a child is due for their first Hepatitis B shot (HB Series Slot 2) and their first DTP shot (DTP Family Slot 1) on the same day, the engine will natively output both recommendations to the UI:
1. `Upcoming: Penta (Slot 1)`  *(from DTP)*
2. `Upcoming: Penta (Slot 2)`  *(from HB)*

This causes the exact same physical product to appear twice in the "Upcoming" or "Due Today" lists, often with conflicting "Dose Numbers" (since the internal `slot_number` of the series dictates the label, rather than the child's actual history with that specific vial).

### Impact
- **User Confusion:** Healthcare workers see two identical vaccines required on the same day with contradictory dose numbers (e.g., "Penta 1" and "Penta 2").
- **Reporting:** Simple count-based analytics of the "Upcoming" list would double-count combination vaccines.

### Potential Fixes / Architectural Considerations (Resolved)
1. **Engine Output Deduplication (Implemented):**
   Added a normalization pass in `_normalize_due_items` that groups all `decision_item`s by `vaccine` and `target_date`. If multiple series ask for the same vaccine on the same day, they are merged.
2. **True Physical Dose Number:**
   Implemented `_true_dose_number()` which calculates the dose label based on actual valid history rather than series slot number, preventing "Penta 1 and Penta 2" contradictions.

**Status**: ✅ Resolved (2026-03-15). Cross-series deduplication and physical dose numbering implemented in `engine.py`.
---
