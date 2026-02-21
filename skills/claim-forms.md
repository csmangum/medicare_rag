---
description: "Medicare claim forms: CMS-1500 for professional claims and UB-04 for institutional claims, with their electronic equivalents (837P and 837I)."
---

# Claim Forms

Medicare claims are submitted on standardized forms mandated by [[hipaa-compliance]] Administrative Simplification provisions. The form determines the data elements required and the processing pathway at the MAC ([[mac-role]]).

## Professional Claims: CMS-1500 / 837P

- Used by physicians, non-physician practitioners, and independent laboratories
- Key fields: patient demographics, insurance info, diagnosis codes ([[icd-10-cm]]), procedure codes ([[cpt-codes]] / [[hcpcs-level-ii]]), [[modifiers]], dates of service, place of service, rendering provider NPI
- Electronic format: ANSI X12 837P transaction

## Institutional Claims: UB-04 / 837I

- Used by hospitals, SNFs, home health agencies, and hospices
- Key fields: admit/discharge dates, type of bill (TOB), revenue codes, diagnosis codes, procedure codes, condition codes, occurrence codes, value codes
- The Type of Bill code (3 digits + frequency code) tells the MAC the claim type: e.g., 131 = hospital outpatient, 111 = hospital inpatient, xx7 = replacement/corrected claim ([[corrected-claims]])
- Electronic format: ANSI X12 837I transaction

## Common Submission Errors

- Mismatched NPI and taxonomy codes
- Invalid or inactive procedure/diagnosis codes
- Missing or invalid referring provider for services requiring referrals
- Place of service code inconsistent with the claim form type

## Connections

Claim forms are the carriers that move coded encounters through the [[claims-lifecycle]]. Errors on the form cause rejections before the claim even reaches [[mac-adjudication]]. Correct form completion is a [[billing-and-coding]] skill and a focus of [[compliance-and-regulations]] training.
