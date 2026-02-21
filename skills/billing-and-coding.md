---
description: "Map of Content for medical billing and coding: HCPCS Level II, ICD-10-CM, CPT, modifiers, code structure, and how standardized codes translate clinical encounters into billable claims."
---

# Billing and Coding

Medical coding is the translation layer between clinical care and reimbursement. Every service rendered must be expressed as a standardized code before it enters the [[claims-lifecycle]], and [[coding-drives-reimbursement]] means that code selection directly determines payment.

## Code Systems

- [[hcpcs-level-ii]] — Healthcare Common Procedure Coding System Level II codes (A0000–V5999) covering supplies, DME, drugs, and services not in CPT; this is the primary code set ingested by the RAG system's HCPCS extractor
- [[icd-10-cm]] — International Classification of Diseases, 10th Revision, Clinical Modification; diagnosis codes that justify medical necessity for every procedure billed
- [[cpt-codes]] — Current Procedural Terminology (AMA-maintained) for physician and outpatient services; HCPCS Level I
- [[modifiers]] — two-character suffixes that alter the meaning of a procedure code without changing the code itself (e.g., -25 for significant, separately identifiable E/M service)

## Coding Principles

- [[medical-necessity-coding]] — every procedure code must be paired with a diagnosis code that demonstrates the service was medically necessary under the applicable [[national-coverage-determinations]] or [[local-coverage-determinations]]
- [[code-specificity-reduces-denials]] — ICD-10-CM's granularity (over 70,000 codes) exists so that the diagnosis precisely matches the clinical scenario, reducing payer queries and denials
- [[unbundling-and-bundling]] — CCI edits define which procedure codes can be billed together; violating bundling rules triggers denials or fraud flags under [[compliance-and-regulations]]

## Code Enrichment in This Project

The RAG system enriches raw code text with semantic context via [[semantic-enrichment-pipeline]]. HCPCS codes receive category labels and related terms based on their prefix (e.g., E-codes → "Durable Medical Equipment"), and ICD-10-CM codes receive chapter-level context (e.g., I-codes → "Diseases of the Circulatory System"). This enrichment improves embedding quality so that natural-language queries like "wheelchair coverage" match E-codes even when the query doesn't contain the code itself.

## Connections

Codes are meaningless without the coverage policies that determine payment — see [[coverage-determination]]. Coded claims enter the [[claims-lifecycle]] for adjudication. Systematic coding errors trigger [[compliance-and-regulations]] scrutiny.
