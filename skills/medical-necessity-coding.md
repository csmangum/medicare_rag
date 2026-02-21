---
description: "Medical necessity in coding: the requirement that every billed service be clinically appropriate for the patient's condition, supported by diagnosis codes and documentation."
---

# Medical Necessity Coding

Medical necessity is the foundational principle of Medicare reimbursement. CMS defines covered services as those that are "reasonable and necessary for the diagnosis or treatment of illness or injury." Every procedure code on a claim must be paired with a diagnosis code that demonstrates the service was medically necessary — this pairing is the core of [[billing-and-coding]].

## How It Works

1. The physician documents the clinical encounter ([[encounter-documentation]])
2. The coder selects the most specific [[icd-10-cm]] diagnosis code supported by the documentation
3. The diagnosis code must appear on the applicable [[national-coverage-determinations]] or [[local-coverage-determinations]] covered-diagnoses list for the procedure code
4. At [[mac-adjudication]], the MAC checks this diagnosis-procedure pairing against coverage policy
5. If the pairing is not on the covered list, the claim is denied for medical necessity

## Common Failure Modes

- **Unspecified diagnosis codes** — using a less-specific code when the documentation supports a more specific one; this is why [[code-specificity-reduces-denials]]
- **Missing documentation** — the diagnosis is valid but the encounter note doesn't support it; [[documentation-quality-determines-revenue]]
- **Wrong diagnosis order** — the primary diagnosis doesn't justify the procedure even though a secondary diagnosis would
- **LCD mismatch** — the MAC's LCD covers the procedure but only for certain diagnoses that differ from the patient's condition

## Connections

Medical necessity connects [[icd-10-cm]] diagnosis codes to [[hcpcs-level-ii]] / [[cpt-codes]] procedure codes. It is enforced through [[coverage-determination]] policies during the [[claims-lifecycle]]. Failed medical necessity is the most common category of denials in [[denial-management]]. The RAG system helps users find which diagnosis codes are covered for specific procedures by searching [[local-coverage-determinations]] and [[national-coverage-determinations]].
