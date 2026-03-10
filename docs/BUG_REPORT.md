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

*(Add new bugs below this line)*
