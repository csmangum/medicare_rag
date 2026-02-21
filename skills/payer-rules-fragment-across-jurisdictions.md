---
description: "Cross-domain claim: national policy sets the floor, but MACs and LCDs create a patchwork of jurisdiction-specific rules that makes a unified knowledge base valuable."
---

# Payer Rules Fragment Across Jurisdictions

This cross-domain claim identifies a structural feature of Medicare that drives complexity: while [[national-coverage-determinations]] provide nationwide rules, the majority of coverage decisions are made at the MAC jurisdiction level through [[local-coverage-determinations]], creating a patchwork of rules that varies by geography.

## The Fragmentation

- There are multiple Part A/B MAC jurisdictions, each with their own LCDs
- DME MACs have separate jurisdictions with their own LCD sets
- The same [[hcpcs-level-ii]] code can be covered in one jurisdiction but not in another
- The same service can require different [[icd-10-cm]] codes to satisfy medical necessity in different jurisdictions
- [[Lcd-articles]] provide jurisdiction-specific billing guidance that differs across MACs

## Impact

- **Multi-state providers** — healthcare systems operating across MAC boundaries must track and comply with multiple LCD sets simultaneously
- **Denial patterns** — a coding practice that produces clean claims in one jurisdiction may generate denials in another
- **Staff training** — [[coding-workflow]] teams need jurisdiction-specific knowledge, multiplying the training burden
- **Appeals** — [[medicare-appeals-process]] arguments must reference the specific MAC's LCD, not a different jurisdiction's policy

## Why This Makes RAG Valuable

A single-source RAG system that indexes LCDs from all jurisdictions (via [[mcd-bulk-data]]) allows users to search across the patchwork. A query like "Is service X covered by MAC jurisdiction Y?" can surface the specific LCD regardless of which MAC issued it. This is a capability that no single MAC portal provides.

## Connections

Jurisdictional fragmentation is a consequence of the MAC system ([[mac-role]]) and the LCD policy mechanism ([[local-coverage-determinations]]). It affects [[billing-and-coding]], [[denial-management]], and [[revenue-cycle-management]] operations for multi-site providers. The RAG system's value proposition ([[rag-bridges-the-knowledge-gap]]) is amplified by this fragmentation because the alternative — manually searching each MAC's website — is impractical.
