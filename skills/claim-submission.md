---
description: "Claim submission: electronic transmission of coded claims to MACs or clearinghouses, including pre-submission edits, scrubbing, and eligibility verification."
---

# Claim Submission

Claim submission is the point where a coded encounter leaves the provider's billing system and enters the payer's processing pipeline. Clean claims — those that pass all front-end edits on the first submission — are a key [[rcm-metrics]] indicator.

## Submission Pathway

1. **Pre-submission scrubbing** — the billing system or clearinghouse applies edits: CCI bundling checks ([[unbundling-and-bundling]]), diagnosis-procedure pairing validation ([[medical-necessity-coding]]), [[frequency-limitations]] flags, and formatting rules
2. **Clearinghouse processing** — most providers submit claims through a clearinghouse that validates formatting, checks for duplicate claims, and routes to the correct MAC
3. **MAC receipt** — the MAC accepts or rejects the claim at the front end; rejections are returned with reason codes and must be corrected and resubmitted
4. **Acknowledgment** — the 999/277CA transaction confirms the MAC received the claim for processing

## Timely Filing

Medicare has a one-year timely filing limit from the date of service (with certain exceptions). Claims submitted after this deadline are denied with no appeal rights. Tracking submission deadlines is a critical [[revenue-cycle-management]] function.

## Connections

Submission follows [[charge-capture]] and [[billing-and-coding]] and precedes [[mac-adjudication]] in the [[claims-lifecycle]]. Clean submission rates affect [[rcm-metrics]] and [[denial-management]] workloads. The [[claim-forms]] must be correctly populated for submission to succeed.
