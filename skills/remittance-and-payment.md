---
description: "Remittance and payment: the ERA/835 transaction that explains what was paid, adjusted, or denied for each claim line item after MAC adjudication."
---

# Remittance and Payment

After [[mac-adjudication]], the MAC issues a remittance advice (RA) explaining the payment decision for each line item. The electronic version (ERA/835) is the standard format for auto-posting payments into the provider's billing system.

## ERA Components

- **Claim-level information** — patient, dates of service, total billed amount, total allowed amount, total paid
- **Line-level adjustments** — for each procedure code: billed amount, allowed amount, payment, contractual adjustment, and patient responsibility
- **Reason codes** — Claim Adjustment Reason Codes (CARCs) and Remittance Advice Remark Codes (RARCs) explain why amounts were adjusted or denied
- **Provider-level summary** — check/EFT number, total payment amount, provider-level adjustments

## Payment Posting

Accurate payment posting — matching ERA data to billed claims — is essential for [[revenue-cycle-management]] reporting. Misposted payments distort [[rcm-metrics]] like net collection rate and days in A/R. Automated posting from 835 data reduces errors but requires correct mapping of adjustment reason codes.

## Identifying Issues

- **Underpayments** — allowed amounts lower than expected may indicate a fee schedule error or incorrect place of service
- **Partial denials** — some line items paid while others denied; the denied lines need [[denial-management]] workup
- **Contractual adjustments** — the difference between billed and allowed is written off per the Medicare fee schedule; not appealable

## Connections

Remittance follows [[mac-adjudication]] and feeds [[denial-management]] and [[collections-and-ar]] in the [[claims-lifecycle]]. Understanding reason codes is critical for [[denial-management]] root cause analysis. Payment data drives [[rcm-metrics]] reporting.
