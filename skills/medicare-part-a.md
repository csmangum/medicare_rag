---
description: "Medicare Part A (Hospital Insurance): covers inpatient hospital stays, skilled nursing facility care, hospice, and some home health services. Funded through payroll taxes (FICA)."
---

# Medicare Part A

Part A is the hospital insurance component of Medicare. Most beneficiaries pay no premium because they or their spouse paid Medicare taxes for 40+ quarters. Understanding Part A coverage boundaries matters for [[billing-and-coding]] because Part A claims use institutional claim forms (UB-04/837I) and are adjudicated under different rules than Part B professional claims.

## Covered Services

- **Inpatient hospital stays** — room, board, nursing, drugs, supplies, and operating room costs during an admitted stay; subject to the inpatient-only list and the two-midnight rule
- **Skilled nursing facility (SNF)** — up to 100 days per benefit period following a qualifying 3-day inpatient hospital stay; days 1-20 are fully covered, days 21-100 require a daily coinsurance
- **Hospice care** — comfort-focused care for terminally ill beneficiaries with a life expectancy of 6 months or less; beneficiary elects hospice and waives curative treatment for the terminal condition
- **Home health services** — intermittent skilled nursing and therapy services for homebound beneficiaries; shared between Part A and [[medicare-part-b]] depending on whether a prior inpatient stay occurred

## Benefit Periods

A benefit period starts when the beneficiary is admitted as an inpatient and ends when they have been out of a hospital or SNF for 60 consecutive days. Each new benefit period resets the Part A deductible. There is no limit on the number of benefit periods, but each one carries fresh cost-sharing obligations.

## Connections

Part A institutional claims feed into the [[claims-lifecycle]] through different MAC processing paths than Part B. Part A coverage criteria are defined in [[national-coverage-determinations]] and IOM 100-02 (Benefits Policy Manual), which the RAG system ingests via [[iom-manuals]]. Incorrect Part A billing can trigger [[compliance-and-regulations]] audits, particularly around short inpatient stays and SNF billing.
