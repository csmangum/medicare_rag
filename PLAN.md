**Here's a comprehensive, actionable guide to building a high-quality, real-data corpus for your Medicare-focused RCM agent.** Medicare is almost entirely federal (administered by CMS), so the bulk of authoritative text is at the federal level. "State-level" variation comes primarily through **Local Coverage Determinations (LCDs)** issued by the Medicare Administrative Contractors (MACs) that serve multi-state jurisdictions. There are no true state-specific Medicare coverage policies—Medicare itself is uniform nationwide except where MACs issue LCDs.

All sources below are **official, public, free, and downloadable** (no paywalls, no licensing required for internal use in a POC). Most are updated regularly (quarterly for codes, weekly/monthly for policies). You can script bulk downloads + text extraction (PDF → Markdown/text via PyMuPDF, pdfplumber, or Unstructured) to feed into your RAG system.

### 1. Core Policy & Coverage Language (Highest Value for Your Agent)
**Internet-Only Manuals (IOMs)** – These are the day-to-day operating instructions for Medicare providers, contractors, and auditors. Perfect for coverage rules, billing requirements, medical necessity, etc.

- **Key manuals for RCM**:
  - **100-02 Medicare Benefit Policy Manual** → Coverage criteria, medical necessity, inpatient/outpatient rules.
  - **100-03 Medicare National Coverage Determinations (NCD) Manual** → National policies (e.g., certain procedures, devices, labs).
  - **100-04 Medicare Claims Processing Manual** → Billing, coding, claim submission, modifiers, edits.
  - **100-01 General Information, Eligibility, and Entitlement**; **100-05 Secondary Payer**; **100-08 Program Integrity** (fraud/abuse signals useful for escalation).

- **How to get them**:
  - Main index: https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms
  - Each manual has a landing page with **every chapter as a separate downloadable PDF** (plus crosswalk files). You can download the full set in a few hours.
  - Total: ~20 manuals, hundreds of chapters → thousands of pages of precise policy language.

**Medicare Coverage Database (MCD)** – NCDs + LCDs + Articles (billing/coding guidance that often accompanies LCDs).

- **Bulk downloads** (best for corpus):
  - Go to: https://www.cms.gov/medicare-coverage-database/downloads/downloads.aspx
  - Available ZIPs (each contains ReadMe + dataset + Data Dictionary):
    - Current LCDs
    - Current + retired LCDs
    - Current Articles
    - Current + retired Articles
    - NCDs
    - "Download All Data" (one big ZIP)
  - Format: Mostly Microsoft Access (.MDB) or CSV (with HTML-formatted text for policy language). Excellent for structured ingestion; full narrative text is often in the datasets or linked PDFs.
  - Updated: LCDs/Articles weekly (Thursdays), NCDs in real time (bulk weekly).

- Individual policies: Searchable at https://www.cms.gov/medicare-coverage-database/search.aspx. You can bulk-download PDFs for high-priority topics (e.g., oncology, orthopedics, imaging) or script scraping the top 200–300 most-used LCDs.

### 2. Coding Systems (Structured, Machine-Readable Gold)
**ICD-10-CM (diagnoses) & ICD-10-PCS (procedures)**  
- Official source: CDC/NCHS → https://www.cdc.gov/nchs/icd/icd-10-cm/files.html  
- Files (per fiscal year, Oct 1–Sep 30; plus mid-year updates like April 1, 2026):
  - PDF (guidelines + code lists)
  - XML (structured, best for databases)
  - ZIP for large releases
- Includes: Full code sets, tables, indexes, official guidelines, addenda.  
- Latest: FY2026 (Oct 2025 + April 2026 updates) + historical back to FY2019.

**HCPCS Level II (supplies, drugs, procedures not in CPT)**  
- Official source: CMS Quarterly Update → https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update  
- Format: ZIP containing Excel/CSV with:
  - Alpha-numeric codes
  - Long & short descriptions
  - Medicare-specific coverage, pricing, and administrative data (very useful for your agent)
- Quarterly files (Jan/Apr/Jul/Oct) + annual snapshots. January 2026 file is already out.

**Additional coding resources**:
- ICD-10-CM Official Guidelines (separate PDF each year).
- NCCI edits, MUEs (Medically Unlikely Edits) – available on CMS site.

### 3. Regulations & Statute (Legal Foundation)
**42 CFR Chapter IV (Medicare Program)**  
- Full text: https://www.ecfr.gov/current/title-42/chapter-IV  
- Key parts for RCM:
  - Part 405–429: General Medicare rules, exclusions, payments, prospective payment systems (DRG, APC), conditions of participation.
  - Part 411: Exclusions & limitations on payment.
  - Part 412/419: Inpatient/outpatient PPS.
  - Part 414: Part B payment.
  - Part 426: NCD/LCD review process.
- Easily scrape/export sections (or use eCFR API if available).

**Social Security Act – Title XVIII** (the actual law creating Medicare)  
- Full text: https://www.ssa.gov/OP_Home/ssact/title18/1800.htm (HTML, easy to parse).

**Federal Register**  
- All proposed/final Medicare rules (payment updates, policy changes). Search "Medicare" on federalregister.gov; download PDFs or use their bulk data.

### 4. State-Level / Regional Variation
- **LCDs by MAC Jurisdiction** → This is the closest thing to "state-level" Medicare text. There are currently 7 A/B MAC jurisdictions (covering groups of states) + separate DME MACs.
  - Find your jurisdiction: https://www.cms.gov/medicare/coding-billing/medicare-administrative-contractors-macs/who-are-macs
  - Each MAC publishes its LCDs on its own site **and** in the national MCD.
  - For corpus: Use the MCD bulk LCD downloads (they include jurisdiction metadata) + optionally scrape the top LCDs from the 7 MAC websites if you need jurisdiction-specific formatting.

- True state-level: Very limited for pure Medicare.  
  - Dual eligibles (Medicare + Medicaid) → State Medicaid manuals sometimes reference Medicare coordination (search "[State] Medicaid Provider Manual").  
  - Medigap → States can add consumer protections beyond federal minimums (guaranteed issue, etc.). Varies by state; documents on state insurance dept. sites.  
  - Provider licensing/scope-of-practice → State boards, but not core for coding/coverage.

### Recommended Corpus-Building Plan (POC-Friendly)
**Phase 1 (1–2 days, core RAG)**  
- Download all IOM chapter PDFs (focus on 100-02, 100-03, 100-04 first).  
- Download latest ICD-10-CM/PCS + HCPCS ZIPs.  
- Download MCD "All Data" + NCD ZIP.  
- Extract text from PDFs; store as Markdown or plain text chunks with metadata (manual/chapter, date, NCD/LCD ID, jurisdiction).

**Phase 2 (1 week)**  
- Script bulk download of all current LCDs/Articles from MCD (or top 100–200 by volume).  
- Add relevant 42 CFR parts + SSA Title XVIII.  
- Include annual Medicare & You handbook + key MLN fact sheets.

**Phase 3 (ongoing)**  
- Subscribe to CMS email lists (MCD updates, IOM transmittals, HCPCS quarterly).  
- Re-pull code files quarterly and policy bulk monthly.  
- Version everything (e.g., folder structure: `corpus/2026-02-15/iom/100-02/ch1.pdf`, `codes/icd10-cm-fy2026/`).

**Tools & Tips**  
- Text extraction: Use LangChain/Unstructured or simple Python scripts.  
- Metadata: Always capture source URL, effective date, revision date, jurisdiction (for LCDs).  
- Size estimate: A few hundred MB compressed; manageable for local RAG (or chunk + embed in vector DB).  
- Legal note: All this is public domain for government works → fine for training/RAG in a POC. For production HIPAA environment, keep the corpus read-only and log access.

This corpus will give your agent **exact, citeable policy language** for prior-auth checks, coding suggestions, medical necessity, denial appeals, etc.—far better than generic LLM knowledge.