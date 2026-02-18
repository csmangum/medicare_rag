# Medicare RAG Index — Validation & Evaluation Report

*Generated 2026-02-18 00:32:27*

## Index Validation

- **Result:** PASSED
- **Checks:** 23/23 passed
- **Total documents:** 36090

- **Source distribution:** {'iom': 17238, 'mcd': 9847, 'codes': 9005}
- **Content length:** min=15, max=4850, median=467, mean=555, p5=83, p95=989
- **Embedding dimension:** 384

## Retrieval Evaluation (k=5)

### Summary

| Metric | Value |
|--------|-------|
| Questions | 63 |
| Hit rate | 46/63 (73.0%) |
| MRR | 0.6090 |
| Avg Precision@5 | 0.5175 |
| Avg Recall@5 | 0.5952 |
| Avg NDCG@5 | 0.9229 |

### Latency

- median: 6 ms, p95: 8 ms, p99: 11 ms

### By category

| Category | n | Hit rate | MRR | P@k | R@k | NDCG@k |
|----------|---|----------|-----|-----|-----|--------|
| abbreviation | 5 | 60% | 0.340 | 0.280 | 0.500 | 0.950 |
| appeals_denials | 5 | 60% | 0.467 | 0.400 | 0.600 | 0.943 |
| claims_billing | 6 | 100% | 1.000 | 0.933 | 1.000 | 0.979 |
| code_lookup | 7 | 57% | 0.500 | 0.486 | 0.571 | 0.680 |
| coding_modifiers | 5 | 80% | 0.800 | 0.600 | 0.400 | 0.981 |
| compliance | 3 | 100% | 0.556 | 0.400 | 1.000 | 0.915 |
| consistency | 4 | 100% | 0.667 | 0.500 | 0.500 | 0.964 |
| cross_source | 4 | 100% | 1.000 | 0.950 | 0.583 | 0.987 |
| edge_case | 4 | 75% | 0.500 | 0.450 | 0.417 | 0.971 |
| lcd_policy | 6 | 33% | 0.333 | 0.267 | 0.167 | 0.839 |
| payment | 3 | 100% | 1.000 | 0.867 | 1.000 | 0.982 |
| policy_coverage | 6 | 67% | 0.500 | 0.433 | 0.667 | 0.974 |
| semantic_retrieval | 5 | 60% | 0.500 | 0.320 | 0.600 | 0.975 |

### By difficulty

| Difficulty | n | Hit rate | MRR | P@k | R@k | NDCG@k |
|------------|---|----------|-----|-----|-----|--------|
| easy | 9 | 67% | 0.556 | 0.511 | 0.537 | 0.758 |
| hard | 16 | 62% | 0.512 | 0.438 | 0.479 | 0.911 |
| medium | 38 | 79% | 0.662 | 0.553 | 0.658 | 0.967 |

### By expected source

| Source | n | Hit rate | MRR | P@k | R@k | NDCG@k |
|--------|---|----------|-----|-----|-----|--------|
| codes | 18 | 72% | 0.667 | 0.578 | 0.472 | 0.860 |
| iom | 52 | 81% | 0.671 | 0.562 | 0.644 | 0.967 |
| mcd | 16 | 69% | 0.573 | 0.487 | 0.312 | 0.922 |

### Consistency (avg Jaccard): 0.733
- **cardiac_rehab:** 0.667
- **wheelchair:** 0.800

### Per-question results

| Status | Question ID | P@k | NDCG@k | Rank | Category | Difficulty |
|--------|----------|-----|--------|------|----------|------------|
| PASS | iom_part_b_coverage | 0.40 | 0.96 | 2 | policy_coverage | easy |
| PASS | iom_part_a_inpatient | 0.60 | 0.90 | 2 | policy_coverage | easy |
| PASS | iom_skilled_nursing | 0.60 | 0.98 | 1 | policy_coverage | medium |
| PASS | iom_home_health | 1.00 | 1.00 | 1 | policy_coverage | medium |
| FAIL | iom_preventive_services | 0.00 | 1.00 | — | policy_coverage | easy |
| FAIL | iom_medical_necessity | 0.00 | 1.00 | — | policy_coverage | medium |
| PASS | claims_processing_overview | 1.00 | 0.96 | 1 | claims_billing | easy |
| PASS | claims_electronic_submission | 1.00 | 0.99 | 1 | claims_billing | medium |
| PASS | claims_timely_filing | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | billing_outpatient_hospital | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | billing_physician_services | 0.80 | 0.96 | 1 | claims_billing | medium |
| PASS | secondary_payer | 0.80 | 0.96 | 1 | claims_billing | medium |
| PASS | modifier_bilateral | 1.00 | 1.00 | 1 | coding_modifiers | medium |
| PASS | modifier_cpt_general | 0.60 | 0.99 | 1 | coding_modifiers | easy |
| PASS | modifier_59 | 0.80 | 0.98 | 1 | coding_modifiers | medium |
| PASS | modifier_25 | 0.60 | 0.99 | 1 | coding_modifiers | medium |
| FAIL | modifier_26_tc | 0.00 | 0.94 | — | coding_modifiers | medium |
| PASS | hcpcs_codes_general | 1.00 | 1.00 | 1 | code_lookup | easy |
| PASS | hcpcs_dme | 1.00 | 1.00 | 1 | code_lookup | medium |
| PASS | hcpcs_drug_codes | 1.00 | 1.00 | 1 | code_lookup | medium |
| FAIL | icd10_diabetes_foot_ulcer | 0.00 | 0.89 | — | code_lookup | medium |
| FAIL | icd10_hypertension | 0.00 | 0.00 | — | code_lookup | easy |
| FAIL | icd10_chest_pain | 0.00 | 0.00 | — | code_lookup | easy |
| PASS | icd10_copd | 0.40 | 0.88 | 2 | code_lookup | medium |
| FAIL | lcd_cardiac_rehab | 0.00 | 0.73 | — | lcd_policy | hard |
| PASS | lcd_hyperbaric_oxygen | 0.60 | 0.95 | 1 | lcd_policy | hard |
| PASS | ncd_coverage_criteria | 1.00 | 1.00 | 1 | lcd_policy | medium |
| FAIL | lcd_physical_therapy | 0.00 | 0.86 | — | lcd_policy | hard |
| FAIL | lcd_imaging_advanced | 0.00 | 0.50 | — | lcd_policy | hard |
| FAIL | mcd_wound_care | 0.00 | 1.00 | — | lcd_policy | hard |
| FAIL | appeals_general | 0.00 | 1.00 | — | appeals_denials | medium |
| FAIL | appeals_power_wheelchair | 0.00 | 0.84 | — | appeals_denials | hard |
| PASS | appeals_levels | 0.40 | 0.96 | 1 | appeals_denials | medium |
| PASS | denial_reasons | 0.60 | 0.91 | 3 | appeals_denials | medium |
| PASS | redetermination_timeline | 1.00 | 1.00 | 1 | appeals_denials | medium |
| PASS | rehab_coverage | 1.00 | 1.00 | 1 | cross_source | medium |
| PASS | diabetes_management_crossref | 1.00 | 1.00 | 1 | cross_source | hard |
| PASS | dme_coverage_and_codes | 0.80 | 0.95 | 1 | cross_source | hard |
| PASS | laboratory_tests_billing | 1.00 | 1.00 | 1 | cross_source | hard |
| FAIL | sem_medical_necessity_natural | 0.00 | 1.00 | — | semantic_retrieval | medium |
| FAIL | sem_prior_auth | 0.00 | 0.93 | — | semantic_retrieval | medium |
| PASS | sem_ambulance_coverage | 1.00 | 1.00 | 1 | semantic_retrieval | medium |
| PASS | sem_copay_deductible | 0.20 | 0.97 | 2 | semantic_retrieval | medium |
| PASS | sem_surgery_coverage | 0.40 | 0.98 | 1 | semantic_retrieval | medium |
| FAIL | abbrev_snf | 0.00 | 1.00 | — | abbreviation | medium |
| FAIL | abbrev_dme | 0.00 | 0.91 | — | abbreviation | medium |
| PASS | abbrev_asc | 0.20 | 0.95 | 2 | abbreviation | medium |
| PASS | abbrev_mac | 1.00 | 0.97 | 1 | abbreviation | medium |
| PASS | abbrev_opps | 0.20 | 0.92 | 5 | abbreviation | hard |
| PASS | edge_very_short | 1.00 | 1.00 | 1 | edge_case | easy |
| PASS | edge_specific_manual | 0.60 | 0.93 | 2 | edge_case | hard |
| PASS | edge_multi_concept | 0.20 | 0.96 | 2 | edge_case | hard |
| FAIL | edge_negation | 0.00 | 0.99 | — | edge_case | hard |
| PASS | consistency_cardiac_rehab_1 | 1.00 | 1.00 | 1 | consistency | medium |
| PASS | consistency_cardiac_rehab_2 | 0.60 | 0.98 | 1 | consistency | medium |
| PASS | consistency_wheelchair_1 | 0.20 | 0.94 | 3 | consistency | medium |
| PASS | consistency_wheelchair_2 | 0.20 | 0.94 | 3 | consistency | medium |
| PASS | program_integrity | 0.60 | 0.94 | 1 | compliance | medium |
| PASS | documentation_requirements | 0.40 | 0.88 | 3 | compliance | medium |
| PASS | enrollment_requirements | 0.20 | 0.93 | 3 | compliance | medium |
| PASS | payment_drg | 0.60 | 0.98 | 1 | payment | hard |
| PASS | payment_apc | 1.00 | 0.99 | 1 | payment | hard |
| PASS | payment_physician_fee_schedule | 1.00 | 0.98 | 1 | payment | hard |
