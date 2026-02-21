---
description: "Patient access: front-end RCM operations including scheduling, registration, insurance verification, and prior authorization that set up downstream billing success."
---

# Patient Access

Patient access is the front door of [[revenue-cycle-management]]. Every process error at this stage — wrong insurance, missing authorization, incorrect demographics — propagates through the [[claims-lifecycle]] as a denial. Getting patient access right is the cheapest way to prevent downstream revenue loss.

## Functions

- **Scheduling** — matching the patient's needs with available providers and time slots; capturing the reason for visit to anticipate [[billing-and-coding]] requirements
- **Registration** — collecting and verifying patient demographics, insurance information, and consent forms; creating or updating the patient account
- **Insurance verification** — confirming active coverage, benefit details, and coordination of benefits; for Medicare, this means verifying [[medicare-eligibility]], active Part coverage, and MSP status
- **Prior authorization** — obtaining advance payer approval for services that require it; primarily a [[medicare-part-c]] requirement but some Part B services (e.g., certain DME items) also require prior auth
- **Financial counseling** — estimating patient responsibility, collecting copays/deductibles, and issuing [[advance-beneficiary-notices]] when Medicare coverage is uncertain

## Connections

Patient access feeds accurate data into [[claim-forms]] and [[claim-submission]]. Verification failures cause [[denial-management]] workloads. Prior authorization gaps create coverage denials at [[mac-adjudication]]. The quality of front-end data collection is a leading indicator of [[rcm-metrics]] performance.
