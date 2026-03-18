# Clinical Scenario Simulator (CSS)

## Overview
The Clinical Scenario Simulator is a UI-driven framework for creating, managing, and executing clinical test scenarios for the vaccination engine. It transitions the testing process from code-heavy, developer-centric JSON files to a user-friendly, database-backed web interface.

## Core Components

### 1. `TestScenario` Model
- **History**: Stores vaccination history as a JSON list.
- **Expected Outcomes**: Defines expected `Due`, `Upcoming`, `Missing`, `Blocked`, and `Invalid` vaccines.
- **Run Status**: Tracks `last_status` (pass/fail), `last_run_at`, and detailed `last_result`.

### 2. `ScenarioRunner` Service
- Executes scenarios using a database **savepoint**.
- Creates temporary `Child` and `VaccinationRecord` objects.
- Runs the `VaccinationEngine` and compares outcomes.
- **Transaction Rollback**: Ensures no test data persists in the database.

### 3. Management Commands
- `import_scenarios`: Migrates legacy `tests/scenarios.json` into the database.
- `run_scenarios`: CLI runner for CI/CD integration.

## Key Features
- **UI Editor**: Dynamic form for defining complex vaccination histories.
- **Comparison Table**: Clear visual diff between what the scenario expected and what the engine actually returned.
- **Stats Dashboard**: High-level overview of the test suite health.
- **Export/Import**: Move scenarios between environments.

## Maintenance
Scenarios should be updated via the **Settings -> Scenarios** tab in the PNI application. When policy rules change (e.g., offsets or dependencies), the expected outcomes in the simulators may need adjustment to reflect the new clinical reality.
