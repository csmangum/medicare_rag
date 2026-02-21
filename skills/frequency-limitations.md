---
description: "Coverage frequency limitations: per-beneficiary caps on how often Medicare will pay for specific services (e.g., one screening colonoscopy per 10 years)."
---

# Frequency Limitations

Many Medicare-covered services have frequency limitations that restrict how often the service can be billed per beneficiary within a defined time period. These limits are encoded in [[national-coverage-determinations]], [[local-coverage-determinations]], and CMS transmittals, and are enforced during [[mac-adjudication]].

## Examples

- **Screening colonoscopy** — once every 10 years (or 4 years for high-risk beneficiaries)
- **Bone density testing** — once every 24 months
- **Diabetic testing supplies** — quantity limits per month based on insulin-dependent vs. non-insulin-dependent status
- **Physical therapy** — annual financial cap with exceptions process
- **DME rentals** — many [[hcpcs-level-ii]] E-codes have rental period limits before ownership transfers

## Billing Impact

When a frequency limit is reached, the next occurrence of the service will be denied unless the provider can document medical necessity that qualifies for an exception. If the provider expects a denial, an [[advance-beneficiary-notices]] should be issued. Tracking frequency limits is part of [[claim-submission]] scrubbing in the [[claims-lifecycle]].

## Connections

Frequency limitations are specified in [[coverage-determination]] policies. They affect [[billing-and-coding]] timing decisions and [[denial-management]] when claims exceed the limit. The RAG system can surface frequency rules from LCD text and IOM references when users ask "how often can I bill X?"
