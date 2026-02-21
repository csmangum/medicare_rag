---
description: "Eligibility verification: confirming a patient's Medicare enrollment, part coverage, benefit period status, and secondary insurance before rendering services."
---

# Eligibility Verification

Eligibility verification is the process of confirming that a patient has active Medicare coverage on the date of service. It is the first financial checkpoint in [[revenue-cycle-management]] and a critical function of [[patient-access]].

## Verification Points

- **Active enrollment** — is the beneficiary currently enrolled in [[medicare-part-a]], [[medicare-part-b]], or both?
- **Benefit period status** — for Part A inpatient claims, has the beneficiary's benefit period deductible been met? How many SNF days remain?
- **Part C enrollment** — is the beneficiary in a [[medicare-part-c]] Medicare Advantage plan? If so, claims go to the MA plan, not the MAC
- **Secondary payer** — does the beneficiary have other insurance that should be billed first under Medicare Secondary Payer rules? ([[medicare-eligibility]])
- **Part D** — for outpatient drugs, is the beneficiary enrolled in a [[medicare-part-d]] plan?

## Verification Methods

- **270/271 electronic transaction** — the HIPAA-mandated eligibility inquiry/response; real-time or batch
- **CMS HETS** — the HIPAA Eligibility Transaction System for Medicare-specific verification
- **MAC web portals** — some MACs offer provider portal access for eligibility lookups

## Connections

Failed eligibility verification leads to eligibility denials in [[mac-adjudication]], which are among the most preventable denial types in [[denial-management]]. Verification is a front-end [[patient-access]] function. The beneficiary's enrollment status ties back to [[medicare-enrollment-periods]] and [[medicare-eligibility]] rules that the RAG system can surface from [[iom-manuals]].
