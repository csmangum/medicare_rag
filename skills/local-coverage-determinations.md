---
description: "Local Coverage Determinations (LCDs): MAC-issued regional policies specifying coverage criteria, covered diagnosis codes, and utilization limits for services within a jurisdiction."
---

# Local Coverage Determinations

LCDs are coverage policies issued by individual MACs ([[mac-role]]) for their jurisdiction. They fill the gaps where no [[national-coverage-determinations]] exists and are a primary reason why [[payer-rules-fragment-across-jurisdictions]] — the same service may be covered in one MAC jurisdiction but not in another.

## Characteristics

- **Regional scope** — each LCD applies only within the issuing MAC's jurisdiction
- **MAC discretion** — MACs can develop LCDs based on their own evidence review, though they must align with national policy where NCDs exist
- **Frequent updates** — LCDs are revised more often than NCDs, with changes communicated through articles and transmittals
- **Covered diagnoses list** — most LCDs include a list of [[icd-10-cm]] codes that satisfy [[medical-necessity-coding]] for the covered procedure codes

## LCD Structure

A typical LCD contains:
- **Coverage indications** — clinical circumstances under which the service is considered reasonable and necessary
- **Limitations** — frequency caps ([[frequency-limitations]]), age restrictions, and prerequisite treatments
- **Covered ICD-10-CM codes** — the diagnosis codes that establish medical necessity
- **Covered HCPCS/CPT codes** — the procedure codes to which the LCD applies
- **Sources of information** — clinical evidence and CMS references supporting the policy

## LCD Data in This Project

The RAG system downloads LCD data as part of the [[mcd-bulk-data]] set. The CSV export includes LCD_ID, title, jurisdiction, effective date, and the full policy text (often as HTML that the [[extraction-pipeline]] strips). This makes LCDs searchable alongside NCDs and code definitions.

## Connections

LCDs are subordinate to [[national-coverage-determinations]] but control coverage where no NCD exists. They are enforced during [[mac-adjudication]] and directly determine [[denial-management]] outcomes. LCD-specific billing guidance appears in [[lcd-articles]]. Providers must know their MAC and applicable LCDs to code correctly ([[billing-and-coding]]).
