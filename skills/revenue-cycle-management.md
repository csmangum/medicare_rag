---
description: "Map of Content for Revenue Cycle Management: the end-to-end business process from patient scheduling through final payment collection, encompassing front-end, mid-cycle, and back-end operations."
---

# Revenue Cycle Management

Revenue Cycle Management (RCM) is the financial backbone of healthcare delivery. It encompasses every administrative and clinical step required to capture, manage, and collect revenue from patient services. In the Medicare context, RCM is uniquely complex because [[medicare-is-rules-driven-documentation]] and [[payer-rules-fragment-across-jurisdictions]].

## Front-End Operations

- [[patient-access]] — scheduling, registration, insurance verification, and prior authorization; errors here cascade through the entire cycle
- [[eligibility-verification]] — confirming Medicare enrollment, Part coverage, secondary insurance, and benefit period status before services are rendered
- [[prior-authorization]] — some Medicare Advantage plans and certain Part B services require advance approval; failure to obtain authorization results in denials

## Mid-Cycle Operations

- [[encounter-documentation]] — the clinical record that feeds [[billing-and-coding]]; CDI (Clinical Documentation Improvement) programs work to ensure documentation supports the highest appropriate code specificity because [[code-specificity-reduces-denials]]
- [[charge-capture]] — translating orders, procedures, and supplies into billable line items; missed charges represent direct revenue loss
- [[coding-workflow]] — professional and facility coders assign [[hcpcs-level-ii]], [[icd-10-cm]], and [[cpt-codes]] based on encounter documentation; coding accuracy determines whether the claim survives [[mac-adjudication]]

## Back-End Operations

- [[claim-submission]] — batching, scrubbing, and transmitting claims electronically to MACs or clearinghouses
- [[denial-management]] — tracking, categorizing, and working denied claims; the denial rate is a key RCM performance metric
- [[payment-posting]] — matching ERA/835 remittance data to billed charges; identifying underpayments, contractual adjustments, and patient responsibility
- [[collections-and-ar]] — managing accounts receivable aging, patient statements, and bad debt; days in A/R is the primary financial health indicator

## Analytics and Improvement

- [[rcm-metrics]] — key performance indicators: clean claim rate, denial rate, days in A/R, net collection rate, cost to collect
- [[denial-prevention]] — root cause analysis and process improvement to reduce denials at the source rather than working them after the fact

## Connections

RCM is the overarching business process that contains the [[claims-lifecycle]] as a core subprocess. It depends on accurate [[billing-and-coding]], compliance with [[coverage-determination]], and adherence to [[compliance-and-regulations]]. The RAG system described in [[rag-architecture]] serves RCM teams by providing instant access to the rules and policies that govern every step.
