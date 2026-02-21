---
description: "Map of Content for the Medicare claims lifecycle: from encounter documentation through claim submission, MAC adjudication, remittance processing, denials, and the five levels of appeal."
---

# Claims Lifecycle

A Medicare claim is the financial artifact of a clinical encounter. It travels a deterministic path from creation to resolution, and every stage depends on the quality of [[billing-and-coding]] and compliance with [[coverage-determination]] policies. Understanding this lifecycle is essential because [[documentation-quality-determines-revenue]] at every checkpoint.

## Claim Creation

- [[encounter-documentation]] — the clinical note that becomes the source of truth; coders translate it into diagnosis and procedure codes, and auditors verify it supports the billed services
- [[charge-capture]] — the process of recording all billable services, supplies, and drugs at the point of care so nothing is missed before coding
- [[claim-forms]] — CMS-1500 for professional claims, UB-04 for institutional claims; each form has specific field requirements tied to the Medicare part and service type

## Submission and Adjudication

- [[claim-submission]] — electronic transmission (837P/837I) to the MAC or clearinghouse; includes edits for formatting, duplicate detection, and eligibility verification
- [[mac-adjudication]] — the MAC applies [[national-coverage-determinations]], [[local-coverage-determinations]], CCI edits, fee schedule lookups, and medical necessity checks to produce a payment or denial decision
- [[remittance-and-payment]] — the ERA/835 remittance advice explains what was paid, adjusted, or denied for each line item; posting this accurately drives [[revenue-cycle-management]] reporting

## Denials and Appeals

- [[denial-management]] — categorizing denials (coverage, coding, eligibility, timely filing), identifying root causes, and preventing recurrence; high denial rates signal problems in [[billing-and-coding]] or [[coverage-determination]] compliance
- [[medicare-appeals-process]] — the five levels: Redetermination (MAC), Reconsideration (QIC), ALJ Hearing, Medicare Appeals Council, and Federal Court; each level has strict deadlines and documentation requirements
- [[corrected-claims]] — when errors are discovered before appeal, submitting a corrected claim (TOB xx7 or frequency code 7) is faster than the appeals process

## Connections

Claims depend on correct [[billing-and-coding]]. Coverage denials trace back to [[coverage-determination]] gaps. The entire lifecycle is a core subprocess of [[revenue-cycle-management]]. Systematic claim errors create [[compliance-and-regulations]] exposure. The RAG system helps users query coverage policies and coding rules to prevent denials before they happen — see [[rag-architecture]].
