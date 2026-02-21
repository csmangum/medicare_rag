---
description: "Payment posting: matching ERA/835 remittance data to billed charges, identifying underpayments, and updating accounts receivable."
---

# Payment Posting

Payment posting is the back-end [[revenue-cycle-management]] process of recording payments and adjustments from [[remittance-and-payment]] data against the corresponding billed claims. Accurate posting is essential for financial reporting and [[rcm-metrics]].

## Process

1. **Receive ERA/835** — the electronic remittance advice is received from the MAC or clearinghouse
2. **Auto-posting** — the billing system matches ERA data to open claims and applies payments, contractual adjustments, and patient responsibility amounts
3. **Exception handling** — claims that don't auto-match (mismatched amounts, unrecognized adjustments, partial denials) go to a manual review queue
4. **Patient billing** — after insurance payment is posted, any remaining patient responsibility (deductible, coinsurance) generates a patient statement
5. **Reconciliation** — bank deposits are reconciled against posted payments to ensure no funds are lost

## Common Issues

- Payments posted to the wrong patient account
- Contractual adjustments not recognized, inflating accounts receivable
- Denied line items not routed to [[denial-management]] for follow-up
- Manual payments (paper checks) not matched to ERAs

## Connections

Payment posting follows [[remittance-and-payment]] in the [[claims-lifecycle]] and feeds [[collections-and-ar]]. Posting accuracy directly affects [[rcm-metrics]] reporting. Unresolved posting exceptions can mask [[denial-management]] issues.
