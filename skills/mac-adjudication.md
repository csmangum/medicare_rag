---
description: "MAC adjudication: the process by which a Medicare Administrative Contractor evaluates a claim against coverage policies, fee schedules, and edits to produce a payment or denial decision."
---

# MAC Adjudication

Adjudication is the decision-making step where the MAC ([[mac-role]]) determines whether to pay, reduce, or deny each line item on a submitted claim. It is the moment where [[billing-and-coding]] accuracy meets [[coverage-determination]] policy.

## Adjudication Steps

1. **Eligibility check** — verify the beneficiary was enrolled in the applicable Medicare part on the date of service ([[medicare-eligibility]])
2. **Duplicate check** — confirm the claim is not a duplicate of a previously processed claim
3. **Coverage policy application** — check the procedure-diagnosis pairing against applicable [[national-coverage-determinations]] and [[local-coverage-determinations]]
4. **CCI edits** — apply Correct Coding Initiative edits ([[unbundling-and-bundling]]) to detect improper code combinations
5. **Fee schedule lookup** — determine the allowed amount from the applicable fee schedule (MPFS for physician services, DMEPOS for DME, OPPS for hospital outpatient)
6. **Benefit calculation** — apply the beneficiary's deductible, coinsurance, and any MSP (secondary payer) rules
7. **Payment or denial** — issue the remittance advice ([[remittance-and-payment]]) with payment amounts and adjustment reason codes

## Denial Reasons

Common denial reason codes at adjudication:
- Medical necessity (the diagnosis doesn't support the procedure)
- Non-covered service (no NCD/LCD supports coverage)
- Duplicate claim
- Timely filing exceeded
- Beneficiary not eligible on date of service

## Connections

Adjudication is the central decision point in the [[claims-lifecycle]]. Its outcome drives [[remittance-and-payment]], [[denial-management]], and potentially the [[medicare-appeals-process]]. The RAG system helps users understand why claims are denied by surfacing the coverage policies and coding rules that the MAC applied.
