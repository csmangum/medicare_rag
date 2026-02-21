---
description: "RCM performance metrics: clean claim rate, denial rate, days in A/R, net collection rate, and other KPIs that measure revenue cycle health."
---

# RCM Metrics

Revenue cycle performance is measured through a set of key performance indicators (KPIs) that quantify the efficiency and effectiveness of each stage in [[revenue-cycle-management]]. These metrics guide improvement efforts and benchmark against industry standards.

## Key Metrics

- **Clean claim rate** — percentage of claims accepted on first submission without rejection or denial; target: >95%; driven by [[billing-and-coding]] accuracy and [[claim-submission]] quality
- **First-pass denial rate** — percentage of claims denied on initial adjudication; target: <5%; reflects [[medical-necessity-coding]] accuracy and [[coverage-determination]] compliance
- **Days in A/R** — average number of days between claim submission and payment; target: <40 days for Medicare; affected by every stage of the [[claims-lifecycle]]
- **Net collection rate** — percentage of allowed charges actually collected; target: >95%; measures effectiveness of [[denial-management]] and [[collections-and-ar]]
- **Cost to collect** — total RCM operational cost as a percentage of net revenue; lower is better; drives decisions about staffing, automation, and outsourcing
- **Denial overturn rate** — percentage of appealed denials that are reversed; measures [[medicare-appeals-process]] effectiveness
- **Point-of-service collections** — percentage of patient responsibility collected at time of service; driven by [[patient-access]] and [[eligibility-verification]]

## Using Metrics

Metrics should be trended over time, segmented by payer (Medicare vs. commercial), service line, and denial category. A sudden increase in denial rate for a specific [[hcpcs-level-ii]] code range may signal an LCD change that the RAG system ([[rag-architecture]]) can help identify.

## Connections

RCM metrics are the feedback mechanism for [[revenue-cycle-management]]. They connect to every stage: [[patient-access]] (point-of-service collections), [[billing-and-coding]] (clean claim rate), [[claims-lifecycle]] (days in A/R), [[denial-management]] (denial rate and overturn rate), and [[collections-and-ar]] (net collection rate).
