---
description: "Internet-Only Manuals (IOMs): CMS-published operational manuals for Medicare, including Benefits Policy (100-02), NCD Manual (100-03), and Claims Processing (100-04)."
---

# IOM Manuals

The Internet-Only Manuals are CMS's comprehensive operational guides for the Medicare program. They contain the detailed rules, procedures, and policies that MACs ([[mac-role]]), providers, and billing staff reference daily. The RAG system ingests three key IOMs as chapter PDFs.

## Ingested Manuals

- **IOM 100-02 (Medicare Benefit Policy Manual)** — defines what Medicare covers and under what circumstances; the authoritative reference for [[medicare-part-a]] and [[medicare-part-b]] benefit rules
- **IOM 100-03 (National Coverage Determinations Manual)** — contains the full text of all [[national-coverage-determinations]]; supplements the NCD data from [[mcd-bulk-data]]
- **IOM 100-04 (Medicare Claims Processing Manual)** — the operational bible for [[billing-and-coding]] and the [[claims-lifecycle]]; covers claim form instructions, [[modifiers]], CCI edits, fee schedule application, and remittance processing

## PDF Structure

Each IOM is organized into chapters (e.g., IOM 100-02 Chapter 6 = Hospital Services, IOM 100-04 Chapter 1 = General Billing Requirements). The [[download-pipeline]] scrapes chapter PDFs, and the [[extraction-pipeline]] uses `pdfplumber` to extract text from each chapter, with an `unstructured` fallback for scanned/image PDFs.

## Connections

IOMs are the primary reference for [[coverage-determination]] rules, [[billing-and-coding]] procedures, and [[compliance-and-regulations]] requirements. They are ingested via the [[download-pipeline]], extracted by the [[extraction-pipeline]], chunked by the [[chunking-strategy]], and indexed in the [[vector-store]]. When the RAG system answers a question about Medicare rules, IOM content is often the most authoritative source in the retrieved context.
