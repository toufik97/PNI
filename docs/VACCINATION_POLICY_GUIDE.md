# Vaccination Policy Guide: Sandbox vs. Live

This guide explains how to manage, verify, and synchronize the vaccination policies (rules, doses, and intervals) for the PNI system.

## 1. The Core Concept: The "Gold Standard"
The system is built around a **Source of Truth** located at:
`vaccines/policy_reference.json`

This file contains the "Gold Standard" medical policy. It defines what vaccines exist, their **Series** (e.g., DTP Family), the **Rules** for matches at each dose slot, and inter-series **Dependencies** and **Transitions**.

- **Tests** use this file to build a temporary "Sandbox" to prove the code works.
- **The Live App** uses a database which can be synchronized with this file.

---

## 2. The Verification Workflow

### Step 1: Propose a Change
If the medical policy changes (e.g., minimum age for a DTP dose or a new dependency between vaccines), **do not** change it in the UI first. Instead, update:
`vaccines/policy_reference.json`

### Step 2: Run the Sandbox Tests
Verify that your changes are logically sound by running the automated suite:
```powershell
venv\Scripts\python.exe manage.py test tests.test_scenarios
```
If these pass, it means your new rules correctly handle all historical and edge-case scenarios (like children arriving late).

### Step 3: Audit the Live Database
Before applying changes to your real patients, see how your live database differs from the new policy:
```powershell
venv\Scripts\python.exe scripts/audit_policy.py
```
This will show you a table of **MATCH**, **MISMATCH**, or **MISSING** fields between your "Gold Standard" and your "Actual" app.

---

## 3. Synchronizing the Live App

Once you are satisfied with the audit, you can push the "Gold Standard" rules into your live database:

```powershell
venv\Scripts\python.exe scripts/audit_policy.py --sync
```

> [!WARNING]
> This command modifies your live database. It will create missing vaccines, series, rules, and dependencies to match the policy reference. It uses the `PolicyVersion` designated in the engine.

---

## 4. Live Scenario Verification
Even after syncing, you might want to prove the app is behaving correctly for real-world scenarios without looking at every setting. Run the scenario runner against your **live** database:

```powershell
venv\Scripts\python.exe scripts/test_live_scenarios.py
```

*Note: This script safely creates temporary children in a database transaction and rolls them back, so it won't clutter your real patient list.*

---

## 5. Adding New Vaccines or Series
To add a new vaccine to the system:
1. Add it to the `"vaccines"` list in `policy_reference.json`.
2. Define a `"series"` for it (or add it to an existing series in the `"products"` list).
3. Define the `"rules"` for that series (min age, recommended age, max age, min interval, etc.).
4. (Optional) Add `"transitions"` or `"dependencies"` if they apply to other series.
5. Run `scripts/audit_policy.py --sync`.
6. The new vaccine and its logic will now appear in your UI and be enforced by the engine.
