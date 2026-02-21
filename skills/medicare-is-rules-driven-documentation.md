---
description: "Synthesis claim: Medicare reimbursement is fundamentally a documentation and rules-compliance problem, and the rule surface area exceeds human memory capacity."
---

# Medicare Is Rules-Driven Documentation

This is the foundational claim of the skill graph: Medicare reimbursement is not primarily a clinical problem — it is a documentation and rules-compliance problem. The clinical encounter creates value, but reimbursement depends entirely on whether the documentation and coding satisfy the applicable rules.

## The Rule Surface Area

The combined rule set that governs a single Medicare claim includes:
- CMS statute and regulations
- [[National-coverage-determinations]] (~300 active policies)
- [[Local-coverage-determinations]] (thousands of policies across MAC jurisdictions)
- [[Lcd-articles]] (thousands more)
- CCI edits ([[unbundling-and-bundling]])
- Fee schedule rules (MPFS, OPPS, DMEPOS, CLFS)
- IOM chapters ([[iom-manuals]]) spanning thousands of pages
- [[Modifiers]] logic
- [[Frequency-limitations]]
- [[Stark-law]], [[anti-kickback-statute]], and [[false-claims-act]] requirements

No individual can hold all of this in memory. This is why:
- [[Revenue-cycle-management]] requires specialized teams for each stage
- [[Compliance-program-elements]] formalize institutional knowledge
- [[Coding-audits]] are necessary because human coders inevitably make errors
- The RAG system ([[rag-architecture]]) exists — it makes the full rule corpus searchable

## The Documentation Dependency

The rules are only half the problem. For each rule, the corresponding clinical documentation ([[encounter-documentation]]) must support compliance. [[Documentation-quality-determines-revenue]] because the best code selection is worthless if the encounter note doesn't support it.

## Implications

This rule-driven nature creates both the problem and the opportunity:
- **Problem** — the complexity creates denial risk, compliance risk, and operational cost
- **Opportunity** — because the rules are structured and published, they can be ingested, indexed, and queried by systems like the one described in [[rag-architecture]]

## Connections

This claim underpins the entire skill graph. It motivates [[rag-bridges-the-knowledge-gap]], explains why [[payer-rules-fragment-across-jurisdictions]] is so impactful, and contextualizes every domain in this graph from [[billing-and-coding]] to [[compliance-and-regulations]].
