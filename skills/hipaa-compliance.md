---
description: "HIPAA compliance: privacy, security, and administrative simplification requirements including standard transaction formats (837, 835) and code sets used in Medicare billing."
---

# HIPAA Compliance

The Health Insurance Portability and Accountability Act of 1996 is primarily known for its Privacy and Security Rules, but for [[revenue-cycle-management]], HIPAA's Administrative Simplification provisions are equally important — they mandate the standard transaction formats and code sets that the entire [[claims-lifecycle]] runs on.

## Administrative Simplification

- **Standard transactions** — HIPAA mandates specific ANSI X12 formats for claims (837P/837I), remittance (835), eligibility (270/271), claim status (276/277), and referral authorization (278); these are the electronic backbone of [[claim-submission]] and [[remittance-and-payment]]
- **Standard code sets** — [[icd-10-cm]] for diagnoses, [[cpt-codes]] and [[hcpcs-level-ii]] for procedures, and National Drug Codes (NDC) for drugs; payers cannot require non-standard codes
- **National Provider Identifier (NPI)** — the unique 10-digit identifier for every healthcare provider; required on all transactions

## Privacy Rule

- Protects individually identifiable health information (PHI)
- Requires minimum necessary use and disclosure
- Grants patients rights to access, amend, and receive an accounting of disclosures
- Affects how the RAG system handles any real patient data (the current system uses only public CMS data, not PHI)

## Security Rule

- Requires administrative, physical, and technical safeguards for electronic PHI (ePHI)
- Mandates risk assessments, access controls, audit logging, and encryption
- Applies to the RAG system if it ever processes ePHI

## Connections

HIPAA's transaction standards enable the electronic [[claims-lifecycle]]. Its code set requirements drive [[billing-and-coding]] standardization. The Privacy and Security Rules constrain how [[revenue-cycle-management]] systems handle patient data. HIPAA compliance is an element of [[compliance-program-elements]] and is enforced by the HHS Office for Civil Rights.
