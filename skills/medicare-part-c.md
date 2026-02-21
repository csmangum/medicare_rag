---
description: "Medicare Part C (Medicare Advantage): private health plans that contract with CMS to deliver Part A and B benefits, often with additional coverage and different cost-sharing structures."
---

# Medicare Part C

Medicare Advantage (MA) plans are an alternative to traditional (Original) Medicare. Private insurers contract with CMS to provide all Part A and Part B benefits, often bundling [[medicare-part-d]] prescription drug coverage and adding dental, vision, or hearing benefits. MA plans are paid a capitated rate per enrollee, creating fundamentally different reimbursement dynamics than fee-for-service Medicare.

## Key Differences from Original Medicare

- **Network restrictions** — most MA plans are HMOs or PPOs with provider networks; out-of-network care may not be covered or may cost more
- **Prior authorization** — MA plans frequently require prior authorization for services that Original Medicare covers without it, adding a step to [[revenue-cycle-management]] front-end operations
- **Plan-specific rules** — each MA plan can define its own medical policies, creating additional rule fragmentation beyond what [[local-coverage-determinations]] already introduce; this is a core reason why [[payer-rules-fragment-across-jurisdictions]]
- **Risk adjustment** — MA plans receive higher capitation payments for sicker enrollees, making accurate [[icd-10-cm]] diagnosis coding especially important; HCC (Hierarchical Condition Category) coding is a major compliance focus

## Implications for RCM

MA claims may use different claim submission pathways and may not go through the traditional MAC. [[denial-management]] for MA plans requires understanding each plan's specific policies, appeal processes, and timely filing limits, which may differ from Original Medicare's five-level [[medicare-appeals-process]].

## Connections

MA plans must cover everything Original Medicare covers ([[medicare-part-a]] and [[medicare-part-b]]) but can layer additional rules on top. The RAG system currently focuses on Original Medicare data (IOMs, NCDs, LCDs), but MA-specific coverage policies represent an important expansion opportunity noted in the [[index]] explorations.
