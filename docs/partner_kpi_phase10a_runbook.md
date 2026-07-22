# Phase 10A - Partner KPI Synthetic Coverage

Phase 10A adds synthetic KPI coverage for partner stakeholders that were previously target-only in the Phase 8 scorecard.

## Scope

The evaluator covers:

1. TPA claim turnaround time improvement.
2. Retailer escalations per 1,000 units reduction.
3. Supplier stockout rate.
4. Supplier excess inventory reduction.

These are controlled synthetic evaluations. They are not live partner outcomes and should not be presented as production proof.

## Run

```powershell
.\.venv\Scripts\python.exe scripts\eval_partner_kpi_phase10a.py
```

Outputs:

- `data/partner_kpi_phase10a_eval_50.json`
- `test_data/partner_kpi_phase10a_cases_50.json`

## Current Targets

| Stakeholder | KPI | Target |
| --- | --- | --- |
| TPA | Claim Turnaround Time | >= 30% improvement |
| Retailer | Escalations per 1,000 Units | >= 20% reduction |
| Supplier | Stockout Rate | < 5% |
| Supplier | Excess Inventory | >= 15% reduction |

## Safe Presentation Wording

Use this wording:

> Partner KPI coverage is now instrumented in a controlled synthetic 50-case evaluation for TPA, retailer and supplier workflows. Live validation still requires pilot partner data.

Avoid saying:

> We reduced live claim turnaround, retailer escalations, stockouts or excess inventory.

Those claims require real partner integrations and observation windows.
