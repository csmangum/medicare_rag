---
description: "National Coverage Determinations (NCDs): CMS-issued national policies that define whether Medicare covers specific services, procedures, or technologies across all jurisdictions."
---

# National Coverage Determinations

NCDs are the highest level of Medicare coverage policy below statute. Issued by CMS ([[cms-role]]), they apply nationwide and override any conflicting [[local-coverage-determinations]]. An NCD definitively states whether Medicare covers a service and, if so, under what conditions.

## Characteristics

- **National scope** — all MACs must follow NCDs regardless of jurisdiction
- **Formal process** — NCDs go through a formal evidence review process, often including a Medicare Evidence Development & Coverage Advisory Committee (MEDCAC) review
- **Limited in number** — there are roughly 300 active NCDs, far fewer than the thousands of LCDs, because they address services where CMS determines that national uniformity is needed
- **Published in IOM 100-03** — the NCD Manual contains the full text of all NCDs; the RAG system ingests this via [[iom-manuals]]

## NCD Structure

A typical NCD contains:
- **Indications and limitations of coverage** — the clinical conditions under which the service is covered, including required [[icd-10-cm]] diagnosis codes
- **Covered and non-covered procedure codes** — the [[hcpcs-level-ii]] or [[cpt-codes]] to which the NCD applies
- **Documentation requirements** — what must be in the medical record to support the service
- **Effective date** — when the policy takes effect; changes are communicated via transmittals

## NCD Data in This Project

The RAG system downloads NCD data as part of the [[mcd-bulk-data]] extract. Each NCD becomes a searchable document with metadata (NCD_ID, title, effective date) that enables retrieval when users ask coverage questions.

## Connections

NCDs sit above [[local-coverage-determinations]] in the policy hierarchy. They are enforced during [[mac-adjudication]] in the [[claims-lifecycle]]. When no NCD exists for a service, the MAC's LCD (if any) controls coverage. NCDs are issued by [[cms-role]] and their compliance is audited by [[oig-role]].
