---
description: Entry point for the Medicare Revenue Cycle Management skill graph. Start here to navigate domain knowledge, system architecture, and coding/billing concepts used by the Medicare RAG system.
---

# Medicare RAG Skill Graph

This skill graph encodes the domain knowledge behind a Retrieval-Augmented Generation system for Medicare Revenue Cycle Management. Every node is a standalone concept the agent can read independently, and [[wikilinks between them create a traversable graph]] of Medicare expertise.

## Synthesis

Core arguments that tie the domain together:

- [[medicare-is-rules-driven-documentation]] — Medicare reimbursement is fundamentally a documentation and rules-compliance problem; the RAG system exists because the rule surface area exceeds what any single person can hold in memory
- [[coding-drives-reimbursement]] — the entire revenue cycle hinges on translating clinical encounters into standardized codes that payers adjudicate against coverage policies
- [[rag-bridges-the-knowledge-gap]] — retrieval-augmented generation lets users query the full breadth of CMS manuals, coverage determinations, and code definitions in natural language without memorizing thousands of pages

## Topic MOCs

The domain breaks into seven interconnected areas:

- [[medicare-fundamentals]] — program structure, parts A/B/C/D, eligibility, enrollment, and the agencies that administer them
- [[billing-and-coding]] — HCPCS Level II, ICD-10-CM, CPT, modifiers, and how codes map clinical reality to billable events
- [[coverage-determination]] — National Coverage Determinations, Local Coverage Determinations, Articles, and Advance Beneficiary Notices that define what Medicare will pay for
- [[claims-lifecycle]] — the path a claim travels from encounter through submission, adjudication, payment or denial, and appeals
- [[revenue-cycle-management]] — the business process wrapping clinical care: scheduling, eligibility verification, charge capture, coding, billing, collections, and analytics
- [[compliance-and-regulations]] — CMS rules, HIPAA, OIG guidelines, False Claims Act, and the guardrails that constrain billing behavior
- [[rag-architecture]] — how this project ingests CMS data, embeds it, retrieves relevant chunks, and generates cited answers

## Cross-Domain Claims

- [[documentation-quality-determines-revenue]] — poor clinical documentation cascades through coding, claim adjudication, and appeals, making documentation improvement the highest-leverage intervention in RCM
- [[code-specificity-reduces-denials]] — the more specific the ICD-10 and HCPCS codes, the fewer coverage-policy mismatches and the lower the denial rate
- [[payer-rules-fragment-across-jurisdictions]] — national policy sets the floor, but MACs and LCDs create a patchwork that makes a single-source RAG system valuable

## Explorations Needed

- How do Medicare Advantage (Part C) plan-specific rules layer on top of traditional Medicare coverage policies?
- What is the optimal chunk size for Medicare regulatory text vs. code descriptions vs. LCD narratives?
- Can graph-based retrieval (following wikilinks at query time) outperform flat vector search for multi-hop Medicare questions?
