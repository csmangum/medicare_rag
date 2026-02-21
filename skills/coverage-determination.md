---
description: "Map of Content for Medicare coverage determinations: NCDs, LCDs, Articles, ABNs, and the policies that define what Medicare will and will not pay for."
---

# Coverage Determination

Coverage determination is the policy layer that sits between [[billing-and-coding]] and the [[claims-lifecycle]]. Before a claim is paid, it must satisfy the coverage criteria defined at both the national and local level. This is where [[medicare-is-rules-driven-documentation]] becomes most concrete: the documentation in the medical record must demonstrate that the service meets every criterion in the applicable coverage policy.

## Policy Types

- [[national-coverage-determinations]] — NCDs are binding nationwide policies issued by CMS that define whether Medicare covers a specific service, procedure, or technology; they override any conflicting local policy
- [[local-coverage-determinations]] — LCDs are policies issued by individual MACs ([[mac-role]]) that specify coverage criteria for services within their jurisdiction; they create the regional variation that makes [[payer-rules-fragment-across-jurisdictions]]
- [[lcd-articles]] — supplementary documents that accompany LCDs with billing guidance, coding tips, and utilization parameters; ingested by the RAG system alongside LCDs
- [[advance-beneficiary-notices]] — ABNs notify beneficiaries before a service that Medicare may not pay, shifting financial liability; required when the provider expects a coverage denial

## Coverage Analysis

- [[medical-necessity-coding]] — the linchpin of coverage: every service must be medically necessary for the patient's condition, and the diagnosis code must appear on the LCD's covered-diagnoses list
- [[coverage-gap-identification]] — systematic comparison of NCDs and LCDs to find services that lack explicit coverage policy, creating ambiguity that the RAG system can surface
- [[frequency-limitations]] — many covered services have per-beneficiary frequency caps (e.g., one screening colonoscopy per 10 years) that are encoded in LCDs and enforced at adjudication

## MCD Bulk Data in This Project

The RAG system downloads the MCD bulk data set (LCDs, NCDs, Articles) as ZIP archives, extracts CSV rows, strips HTML, and produces one document per policy. Each document carries metadata (LCD_ID, jurisdiction, effective date) that enables filtered retrieval — see [[rag-architecture]] for the full pipeline.

## Connections

Coverage policies reference specific [[hcpcs-level-ii]] and [[icd-10-cm]] codes. Denied claims due to coverage mismatches feed into the appeals stage of the [[claims-lifecycle]]. Billing for non-covered services without an [[advance-beneficiary-notices]] creates [[compliance-and-regulations]] risk.
