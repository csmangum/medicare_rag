---
description: "Medicare Coverage Database bulk data: ZIP archives containing LCDs, NCDs, and Articles as CSV exports, downloaded and parsed by the RAG system."
---

# MCD Bulk Data

The Medicare Coverage Database (MCD) bulk data export provides structured access to all active and historical [[local-coverage-determinations]], [[national-coverage-determinations]], and [[lcd-articles]]. The RAG system downloads this data as ZIP files and extracts individual policy documents.

## Data Format

The MCD bulk export consists of multiple ZIP files:
- `current_lcd.zip` / `all_lcd.zip` — LCD records as CSV with fields for LCD_ID, title, jurisdiction, effective date, and full policy text (often HTML-encoded)
- `ncd.zip` — NCD records with similar structure
- `current_article.zip` / `all_article.zip` — supplementary articles

Each CSV row represents one coverage policy or article. The policy text fields frequently contain HTML markup that the [[extraction-pipeline]] strips to produce clean text.

## Processing

The extraction pipeline (`extract_mcd()`) handles nested ZIPs (some archives contain inner `*_csv.zip` files), extracts CSV rows, strips HTML using BeautifulSoup, and writes one `.txt` + `.meta.json` per policy document. Metadata includes the policy ID, title, jurisdiction, and effective date, enabling filtered retrieval.

## Connections

MCD data is the primary source for [[coverage-determination]] content in the RAG system. It complements the IOM NCD Manual ([[iom-manuals]]) with more structured, per-policy data. The data is downloaded by the [[download-pipeline]], processed by the [[extraction-pipeline]], chunked by the [[chunking-strategy]], and indexed in the [[vector-store]].
