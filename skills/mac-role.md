---
description: "Medicare Administrative Contractors (MACs): regional entities that process claims, publish LCDs, and conduct medical review on behalf of CMS."
---

# MAC Role

Medicare Administrative Contractors are private companies that CMS contracts with to process Medicare claims in specific geographic jurisdictions. MACs are the operational arm of Medicare — they adjudicate claims, publish [[local-coverage-determinations]], answer provider inquiries, and conduct audits.

## Key Functions

- **Claim processing** — MACs receive, validate, and adjudicate claims ([[mac-adjudication]]) for their jurisdiction, applying national rules and their own LCDs
- **LCD publication** — MACs issue LCDs that define coverage criteria for services within their jurisdiction; these create the regional variation described in [[payer-rules-fragment-across-jurisdictions]]
- **Provider education** — MACs publish articles, FAQs, and billing guidance to help providers submit clean claims
- **Medical review** — MACs conduct pre-payment and post-payment reviews to verify that claims comply with coverage policies and coding rules; this is a primary enforcement mechanism for [[compliance-and-regulations]]

## MAC Jurisdictions

Medicare has separate MAC jurisdictions for Part A/B claims and DME claims. A provider's MAC depends on the provider's geographic location (not the beneficiary's). This jurisdictional structure means that the same service can have different LCD coverage criteria depending on where the provider is located.

## Connections

MACs are central to the [[claims-lifecycle]] because they make the pay/deny decision. Their LCDs are a core data source for [[coverage-determination]] and are ingested by the RAG system via [[mcd-bulk-data]]. MAC audit findings feed into [[compliance-and-regulations]] enforcement. Understanding which MAC covers a provider is a prerequisite for accurate [[billing-and-coding]].
