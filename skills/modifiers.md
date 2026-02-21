---
description: "CPT/HCPCS modifiers: two-character suffixes that alter the meaning of a procedure code without changing the code itself, affecting payment and adjudication."
---

# Modifiers

Modifiers are two-character codes (numeric for CPT, alphanumeric for HCPCS) appended to procedure codes to provide additional information about the service performed. They do not change what the code describes but alter how the claim is processed and paid during [[mac-adjudication]].

## Common Modifiers

- **-25** — significant, separately identifiable E/M service on the same date as a procedure; one of the most audited modifiers
- **-59 / X{EPSU}** — distinct procedural service; used to bypass Correct Coding Initiative (CCI) edits when procedures are truly separate (see [[unbundling-and-bundling]])
- **-26** — professional component only (interpretation) when the technical component is billed separately
- **-TC** — technical component only
- **-LT / -RT** — left side / right side; required for bilateral procedures to specify laterality
- **-76 / -77** — repeat procedure by same / different physician
- **-GA** — waiver of liability on file (indicates a signed [[advance-beneficiary-notices]])
- **-GY** — item or service not covered by Medicare; used for mandatory claim submission
- **-KX** — requirements specified in the medical policy have been met (used with DME and therapy services)

## Modifier Impact on Payment

Modifiers can increase payment (e.g., -22 for increased procedural services), reduce payment (e.g., -52 for reduced services), or change the processing logic (e.g., -59 bypassing a CCI edit). Incorrect modifier usage is a common source of denials in the [[claims-lifecycle]] and a frequent target of [[coding-audits]].

## Connections

Modifiers interact with [[hcpcs-level-ii]] and [[cpt-codes]] on every claim. [[Local-coverage-determinations]] sometimes require specific modifiers to indicate policy compliance. Modifier misuse (especially -25 and -59) is a high-priority area for [[oig-role]] audits and [[compliance-and-regulations]] enforcement.
