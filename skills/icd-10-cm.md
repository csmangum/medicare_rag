---
description: "ICD-10-CM (International Classification of Diseases, 10th Revision, Clinical Modification): the diagnosis code system with 70,000+ codes used to justify medical necessity for every Medicare claim."
---

# ICD-10-CM

ICD-10-CM is the diagnosis classification system used in the United States for all healthcare settings. It provides the diagnostic justification for every procedure billed to Medicare — without an appropriate ICD-10-CM code, the claim lacks [[medical-necessity-coding]] and will be denied.

## Structure

ICD-10-CM codes are alphanumeric, 3–7 characters long, with the format `A00.0000`:

- **Category (3 chars)** — the first letter indicates the chapter (body system or condition type), followed by two digits
- **Subcategory (4th char)** — adds specificity after the decimal point
- **Extensions (5th–7th chars)** — provide laterality, encounter type (initial, subsequent, sequela), and other detail

## Chapter Organization

The RAG system's [[semantic-enrichment-pipeline]] maps codes to their ICD-10-CM chapter to add context:

- A00–B99: Infectious and parasitic diseases
- C00–D49: Neoplasms
- E00–E89: Endocrine, nutritional, and metabolic diseases
- I00–I99: Diseases of the circulatory system
- M00–M99: Musculoskeletal system diseases
- S00–T88: Injury, poisoning, and external causes
- Z00–Z99: Factors influencing health status (screenings, follow-ups, history)

## Coding Principles

- **Code to the highest level of specificity** — [[code-specificity-reduces-denials]] because vague codes trigger payer queries
- **Code what is documented** — coders may not infer diagnoses; the physician must document the condition in the encounter note ([[encounter-documentation]])
- **Sequence matters** — the principal/first-listed diagnosis drives medical necessity and may affect DRG assignment for inpatient claims

## Data Source

CMS distributes ICD-10-CM as an XML file within a ZIP archive. The RAG system's [[extraction-pipeline]] parses the tabular XML to extract code-description pairs, enriches them via [[semantic-enrichment-pipeline]], and indexes them in the [[vector-store]].

## Connections

ICD-10-CM codes pair with [[hcpcs-level-ii]] and [[cpt-codes]] on every claim in the [[claims-lifecycle]]. [[Local-coverage-determinations]] and [[national-coverage-determinations]] specify which diagnosis codes satisfy medical necessity for each covered service. Incorrect diagnosis coding is a primary target of [[coding-audits]] and [[compliance-and-regulations]] enforcement.
