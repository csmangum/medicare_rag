# Medicare RAG Index — Validation & Evaluation Report

*Generated 2026-02-17 04:39:03*

## Index Validation

- **Result:** PASSED
- **Checks:** 23/23 passed
- **Total documents:** 41802

- **Source distribution:** {'iom': 16916, 'mcd': 15881, 'codes': 9005}
- **Content length:** min=1, max=4577, median=488, mean=532, p5=82, p95=989
- **Embedding dimension:** 384

## Retrieval Evaluation (k=5)

### Summary

| Metric | Value |
|--------|-------|
| Questions | 63 |
| Hit rate | 55/63 (87.3%) |
| MRR | 0.8325 |
| Avg Precision@5 | 0.7619 |
| Avg NDCG@5 | 0.9516 |

### Latency

- median: 6 ms, p95: 7 ms, p99: 10 ms

### By category

| Category | n | Hit rate | MRR | P@k | NDCG@k |
|----------|---|----------|-----|-----|--------|
| abbreviation | 5 | 100% | 0.900 | 0.960 | 0.978 |
| appeals_denials | 5 | 100% | 1.000 | 0.920 | 0.992 |
| claims_billing | 6 | 100% | 1.000 | 1.000 | 1.000 |
| code_lookup | 7 | 14% | 0.143 | 0.086 | 0.714 |
| coding_modifiers | 5 | 100% | 1.000 | 0.960 | 1.000 |
| compliance | 3 | 100% | 1.000 | 0.800 | 0.983 |
| consistency | 4 | 100% | 1.000 | 0.950 | 0.989 |
| cross_source | 4 | 100% | 0.675 | 0.700 | 0.908 |
| edge_case | 4 | 100% | 1.000 | 0.900 | 0.984 |
| lcd_policy | 6 | 67% | 0.667 | 0.433 | 0.986 |
| payment | 3 | 100% | 1.000 | 0.933 | 0.993 |
| policy_coverage | 6 | 100% | 1.000 | 0.933 | 0.992 |
| semantic_retrieval | 5 | 100% | 0.850 | 0.720 | 0.958 |

### By difficulty

| Difficulty | n | Hit rate | MRR | P@k | NDCG@k |
|------------|---|----------|-----|-----|--------|
| easy | 9 | 67% | 0.667 | 0.622 | 0.772 |
| hard | 16 | 88% | 0.794 | 0.662 | 0.965 |
| medium | 38 | 92% | 0.888 | 0.837 | 0.988 |

### By expected source

| Source | n | Hit rate | MRR | P@k | NDCG@k |
|--------|---|----------|-----|-----|--------|
| codes | 18 | 67% | 0.567 | 0.556 | 0.862 |
| iom | 52 | 100% | 0.951 | 0.892 | 0.982 |
| mcd | 16 | 88% | 0.828 | 0.738 | 0.981 |

### Consistency (avg Jaccard): 0.483
- **cardiac_rehab:** 0.167
- **wheelchair:** 0.800

### Per-question results

| Status | Question ID | P@k | NDCG@k | Rank | Category | Difficulty |
|--------|-------------|-----|--------|------|----------|------------|
| PASS | iom_part_b_coverage | 1.00 | 1.00 | 1 | policy_coverage | easy |
| PASS | iom_part_a_inpatient | 1.00 | 1.00 | 1 | policy_coverage | easy |
| PASS | iom_skilled_nursing | 1.00 | 1.00 | 1 | policy_coverage | medium |
| PASS | iom_home_health | 1.00 | 1.00 | 1 | policy_coverage | medium |
| PASS | iom_preventive_services | 0.60 | 0.95 | 1 | policy_coverage | easy |
| PASS | iom_medical_necessity | 1.00 | 1.00 | 1 | policy_coverage | medium |
| PASS | claims_processing_overview | 1.00 | 1.00 | 1 | claims_billing | easy |
| PASS | claims_electronic_submission | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | claims_timely_filing | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | billing_outpatient_hospital | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | billing_physician_services | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | secondary_payer | 1.00 | 1.00 | 1 | claims_billing | medium |
| PASS | modifier_bilateral | 1.00 | 1.00 | 1 | coding_modifiers | medium |
| PASS | modifier_cpt_general | 1.00 | 1.00 | 1 | coding_modifiers | easy |
| PASS | modifier_59 | 0.80 | 1.00 | 1 | coding_modifiers | medium |
| PASS | modifier_25 | 1.00 | 1.00 | 1 | coding_modifiers | medium |
| PASS | modifier_26_tc | 1.00 | 1.00 | 1 | coding_modifiers | medium |
| FAIL | hcpcs_codes_general | 0.00 | 1.00 | — | code_lookup | easy |
| FAIL | hcpcs_dme | 0.00 | 1.00 | — | code_lookup | medium |
| FAIL | hcpcs_drug_codes | 0.00 | 1.00 | — | code_lookup | medium |
| FAIL | icd10_diabetes_foot_ulcer | 0.00 | 1.00 | — | code_lookup | medium |
| FAIL | icd10_hypertension | 0.00 | 0.00 | — | code_lookup | easy |
| FAIL | icd10_chest_pain | 0.00 | 0.00 | — | code_lookup | easy |
| PASS | icd10_copd | 0.60 | 1.00 | 1 | code_lookup | medium |
| FAIL | lcd_cardiac_rehab | 0.00 | 1.00 | — | lcd_policy | hard |
| PASS | lcd_hyperbaric_oxygen | 0.60 | 1.00 | 1 | lcd_policy | hard |
| PASS | ncd_coverage_criteria | 1.00 | 1.00 | 1 | lcd_policy | medium |
| FAIL | lcd_physical_therapy | 0.00 | 1.00 | — | lcd_policy | hard |
| PASS | lcd_imaging_advanced | 0.60 | 0.97 | 1 | lcd_policy | hard |
| PASS | mcd_wound_care | 0.40 | 0.95 | 1 | lcd_policy | hard |
| PASS | appeals_general | 1.00 | 1.00 | 1 | appeals_denials | medium |
| PASS | appeals_power_wheelchair | 0.80 | 0.98 | 1 | appeals_denials | hard |
| PASS | appeals_levels | 0.80 | 0.98 | 1 | appeals_denials | medium |
| PASS | denial_reasons | 1.00 | 1.00 | 1 | appeals_denials | medium |
| PASS | redetermination_timeline | 1.00 | 1.00 | 1 | appeals_denials | medium |
| PASS | rehab_coverage | 1.00 | 1.00 | 1 | cross_source | medium |
| PASS | diabetes_management_crossref | 1.00 | 1.00 | 1 | cross_source | hard |
| PASS | dme_coverage_and_codes | 0.20 | 0.77 | 5 | cross_source | hard |
| PASS | laboratory_tests_billing | 0.60 | 0.87 | 2 | cross_source | hard |
| PASS | sem_medical_necessity_natural | 0.60 | 1.00 | 1 | semantic_retrieval | medium |
| PASS | sem_prior_auth | 0.40 | 0.82 | 4 | semantic_retrieval | medium |
| PASS | sem_ambulance_coverage | 1.00 | 1.00 | 1 | semantic_retrieval | medium |
| PASS | sem_copay_deductible | 1.00 | 1.00 | 1 | semantic_retrieval | medium |
| PASS | sem_surgery_coverage | 0.60 | 0.97 | 1 | semantic_retrieval | medium |
| PASS | abbrev_snf | 1.00 | 1.00 | 1 | abbreviation | medium |
| PASS | abbrev_dme | 0.80 | 0.89 | 2 | abbreviation | medium |
| PASS | abbrev_asc | 1.00 | 1.00 | 1 | abbreviation | medium |
| PASS | abbrev_mac | 1.00 | 1.00 | 1 | abbreviation | medium |
| PASS | abbrev_opps | 1.00 | 1.00 | 1 | abbreviation | hard |
| PASS | edge_very_short | 1.00 | 1.00 | 1 | edge_case | easy |
| PASS | edge_specific_manual | 0.80 | 0.96 | 1 | edge_case | hard |
| PASS | edge_multi_concept | 1.00 | 1.00 | 1 | edge_case | hard |
| PASS | edge_negation | 0.80 | 0.98 | 1 | edge_case | hard |
| PASS | consistency_cardiac_rehab_1 | 1.00 | 1.00 | 1 | consistency | medium |
| PASS | consistency_cardiac_rehab_2 | 0.80 | 0.96 | 1 | consistency | medium |
| PASS | consistency_wheelchair_1 | 1.00 | 1.00 | 1 | consistency | medium |
| PASS | consistency_wheelchair_2 | 1.00 | 1.00 | 1 | consistency | medium |
| PASS | program_integrity | 0.80 | 0.96 | 1 | compliance | medium |
| PASS | documentation_requirements | 0.80 | 0.99 | 1 | compliance | medium |
| PASS | enrollment_requirements | 0.80 | 1.00 | 1 | compliance | medium |
| PASS | payment_drg | 0.80 | 0.98 | 1 | payment | hard |
| PASS | payment_apc | 1.00 | 1.00 | 1 | payment | hard |
| PASS | payment_physician_fee_schedule | 1.00 | 1.00 | 1 | payment | hard |
