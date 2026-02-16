# HIPAA Controls for Corporate Deployment of Medicare RAG

This document identifies the HIPAA Security Rule, Privacy Rule, and Breach Notification Rule controls a corporate organization should implement before deploying this Medicare RAG system in a production healthcare environment. Controls are mapped to specific 45 CFR regulatory sections and tied to the concrete components of this codebase.

---

## Table of Contents

1. [Risk Context](#1-risk-context)
2. [Administrative Safeguards (45 CFR 164.308)](#2-administrative-safeguards-45-cfr-164308)
3. [Physical Safeguards (45 CFR 164.310)](#3-physical-safeguards-45-cfr-164310)
4. [Technical Safeguards (45 CFR 164.312)](#4-technical-safeguards-45-cfr-164312)
5. [Privacy Rule Considerations (45 CFR 164.500-534)](#5-privacy-rule-considerations-45-cfr-164500-534)
6. [Breach Notification (45 CFR 164.400-414)](#6-breach-notification-45-cfr-164400-414)
7. [Business Associate Agreements](#7-business-associate-agreements)
8. [Implementation Checklist](#8-implementation-checklist)
9. [Architecture Changes Required](#9-architecture-changes-required)

---

## 1. Risk Context

### What This System Does

This is a Retrieval-Augmented Generation (RAG) system that ingests **publicly available** CMS Medicare data (Internet-Only Manuals, Medicare Coverage Database, ICD-10/HCPCS codes), embeds it into a local ChromaDB vector store, and answers natural-language Medicare Revenue Cycle Management questions via a local Hugging Face LLM.

### Why HIPAA Matters Even With Public Source Data

The corpus itself (CMS manuals, code sets, coverage determinations) is public-domain federal data and contains **no Protected Health Information (PHI)**. However, in a corporate healthcare setting:

- **User queries may contain PHI.** Staff asking questions like *"Patient John Smith DOB 01/15/1950 was denied for CPT 99213 -- what's the appeal basis?"* introduce PHI into the system through the query interface, query logs, and LLM context windows.
- **Query history persists to disk.** The REPL stores readline history at `~/.medicare_rag_query_history`, which may capture PHI from user input.
- **LLM outputs could echo PHI.** If PHI enters the prompt, the generated answer may contain or repeat it.
- **Integration with clinical systems** in production could introduce PHI into metadata filters, retrieval context, or downstream logging.
- **The system runs on infrastructure** (servers, workstations) that may also process or store ePHI, making it part of the broader HIPAA-regulated environment.

### Threat Model Summary

| Threat | Likelihood | Impact | Components Affected |
| --- | --- | --- | --- |
| PHI in user queries logged to disk | High | High | `query.py` (readline history), application logs |
| Unauthorized access to vector store | Medium | Medium | `data/chroma/`, `data/raw/`, `data/processed/` |
| PHI in LLM context/output | High | High | `chain.py` prompt construction, response output |
| Model exfiltration or tampering | Low | Medium | HuggingFace model cache, `data/chroma/` |
| Unencrypted data at rest | Medium | High | All `data/` directories, query history file |
| No authentication on query interface | High | High | `scripts/query.py` REPL, any future API/UI |
| Lack of audit trail | High | Medium | No logging infrastructure currently |

---

## 2. Administrative Safeguards (45 CFR 164.308)

### 2.1 Risk Analysis (164.308(a)(1)(ii)(A)) -- REQUIRED

**Current gap:** No formal risk analysis exists for this system.

**Required actions:**
- Conduct a formal risk assessment covering all components: data ingestion pipeline, vector store, query interface, LLM inference, local file storage, and model cache.
- Document the data flow: `User Query -> Retriever -> ChromaDB -> LLM Prompt -> LLM Response -> User Display`.
- Identify all locations where PHI could be introduced, stored, or transmitted.
- Reassess whenever the system architecture changes (e.g., adding a web UI, switching to a cloud LLM, integrating with EHR).

### 2.2 Risk Management (164.308(a)(1)(ii)(B)) -- REQUIRED

**Required actions:**
- Implement security measures sufficient to reduce risks to a reasonable and appropriate level.
- Prioritize: access controls, encryption, audit logging, and PHI-in-query mitigation.
- Document risk acceptance decisions (e.g., if the organization decides the public corpus data does not require encryption at rest, document why).

### 2.3 Workforce Security (164.308(a)(3)) -- REQUIRED

**Current gap:** No access controls on the system; anyone with shell access can run queries, read the vector store, or modify the corpus.

**Required actions:**
- Define roles: corpus administrator (manages ingestion), query user (runs queries), system administrator (manages infrastructure).
- Implement procedures to ensure only authorized workforce members can access the system.
- Terminate access promptly when workforce members change roles or leave the organization.

### 2.4 Information Access Management (164.308(a)(4)) -- REQUIRED

**Required actions:**
- Implement role-based access to the data directories (`data/raw/`, `data/processed/`, `data/chroma/`).
- Restrict who can run ingestion scripts (`scripts/ingest_all.py`, `scripts/download_all.py`) vs. query scripts (`scripts/query.py`).
- If a web UI or API is added, implement application-level authorization.

### 2.5 Security Awareness and Training (164.308(a)(5)) -- REQUIRED

**Required actions:**
- Train users to **never include patient-identifiable information** in queries when possible.
- Provide guidance on de-identifying questions before querying (e.g., use "a 70-year-old Medicare beneficiary" instead of "John Smith DOB 01/15/1950").
- Include this system in the organization's regular HIPAA security awareness training.
- Provide reminders at the query interface (see Section 9).

### 2.6 Security Incident Procedures (164.308(a)(6)) -- REQUIRED

**Required actions:**
- Include this system in the organization's incident response plan.
- Define what constitutes a security incident for this system (e.g., unauthorized access to query logs containing PHI, model tampering, unauthorized corpus modification).
- Document response procedures specific to this system's components.

### 2.7 Contingency Plan (164.308(a)(7)) -- REQUIRED

**Required actions:**
- **Data backup:** Back up `data/chroma/` (vector store), `data/processed/` (processed corpus), and configuration files. The raw CMS data (`data/raw/`) can be re-downloaded.
- **Disaster recovery:** Document how to rebuild the system from scratch (download -> extract -> chunk -> embed -> store).
- **Emergency mode operations:** Define whether this system is critical for operations and what the fallback is if it's unavailable.

### 2.8 Evaluation (164.308(a)(8)) -- REQUIRED

**Required actions:**
- Periodically evaluate the effectiveness of security controls.
- Include this system in regular security audits and penetration testing.
- Re-evaluate after any significant change (adding web UI, switching LLM provider, cloud deployment).

---

## 3. Physical Safeguards (45 CFR 164.310)

### 3.1 Facility Access Controls (164.310(a)) -- REQUIRED

**Required actions:**
- If running on on-premises hardware: ensure the server is in a physically secured area with controlled access (locked server room, badge access).
- If running on cloud infrastructure: verify the cloud provider's physical security certifications (SOC 2, HIPAA BAA).

### 3.2 Workstation Security (164.310(b)-(c)) -- REQUIRED

**Current gap:** The REPL runs on any workstation with the venv activated. No workstation restrictions.

**Required actions:**
- Define which workstations are authorized to run the query interface.
- Ensure workstations have screen locks, disk encryption, and endpoint protection.
- The query history file (`~/.medicare_rag_query_history`) lives on the user's home directory -- ensure workstation disk encryption covers this.

### 3.3 Device and Media Controls (164.310(d)) -- REQUIRED

**Required actions:**
- Establish procedures for disposing of media containing the vector store or query logs.
- If the system runs on portable devices (laptops), ensure full-disk encryption and remote-wipe capability.
- Sanitize storage media before reuse or disposal (especially `data/` directories and model cache).

---

## 4. Technical Safeguards (45 CFR 164.312)

### 4.1 Access Control (164.312(a)) -- REQUIRED

**Current gap:** No authentication or authorization. Anyone with filesystem access can query, modify, or exfiltrate data.

**Required actions:**

| Control | Implementation |
| --- | --- |
| Unique user identification (164.312(a)(2)(i)) | Assign unique user accounts; do not share the venv or service account. If deploying as a web service, implement user authentication (OAuth2, SAML, LDAP). |
| Emergency access procedure (164.312(a)(2)(ii)) | Document how authorized personnel can access the system in an emergency. |
| Automatic logoff (164.312(a)(2)(iii)) | Configure session timeouts on the query interface. For the REPL, rely on workstation screen lock policies. For a web UI, implement idle session timeout. |
| Encryption and decryption (164.312(a)(2)(iv)) | Encrypt `data/chroma/`, `data/processed/`, query logs, and model cache at rest (see 4.4). |

### 4.2 Audit Controls (164.312(b)) -- REQUIRED

**Current gap:** No audit logging exists. There is no record of who queried what, when, or what was returned.

**Required actions:**
- Implement structured audit logging for every query: timestamp, authenticated user ID, query text, number of documents retrieved, and response summary.
- **Critical decision:** If queries may contain PHI, the audit log itself becomes ePHI and must be protected accordingly. Consider logging a hashed/redacted version of the query, or classifying the audit log as ePHI with appropriate controls.
- Log ingestion events: who ran ingestion, what sources were processed, timestamps.
- Log access to the data directories.
- Retain audit logs per the organization's retention policy (HIPAA requires 6 years for policies/procedures; audit log retention should align).
- Forward logs to a centralized SIEM or log management system.

**Suggested implementation (code-level):**

```python
# Add to src/medicare_rag/query/chain.py or a new src/medicare_rag/audit.py
import logging
import json
from datetime import datetime, timezone

audit_logger = logging.getLogger("medicare_rag.audit")

def log_query_event(user_id: str, query: str, num_docs: int, duration_ms: float):
    audit_logger.info(json.dumps({
        "event": "rag_query",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "query_length": len(query),  # log length, not content, to avoid PHI in logs
        "num_docs_retrieved": num_docs,
        "duration_ms": duration_ms,
    }))
```

### 4.3 Integrity Controls (164.312(c)) -- REQUIRED

**Current gap:** Content hashes exist for incremental indexing (`store.py` uses SHA-256 content hashes) but are not used for tamper detection.

**Required actions:**
- Protect the vector store (`data/chroma/`) from unauthorized modification using filesystem permissions (minimum: `chmod 700` on data directories, owned by a dedicated service account).
- Implement integrity verification for the corpus: compare stored manifest hashes (`manifest.json` SHA-256 hashes) against files on disk periodically.
- Sign or checksum the ChromaDB collection to detect tampering (a poisoned corpus could cause the LLM to generate harmful clinical guidance).
- Protect the LLM model cache from modification (model poisoning attack).

### 4.4 Encryption (164.312(e)) -- ADDRESSABLE

**Current gap:** No encryption at rest. No encryption in transit (local system, but relevant if deployed as a networked service).

**At rest:**
- Enable full-disk encryption (LUKS, BitLocker, FileVault) on any system hosting the `data/` directory, query history, or model cache.
- For cloud deployments: use encrypted volumes (AWS EBS encryption, Azure Disk Encryption, GCP CMEK).
- Consider application-level encryption for the query history file.

**In transit:**
- Currently not applicable (local REPL, local LLM, local ChromaDB).
- **If a web UI or API is added:** enforce TLS 1.2+ for all connections. Terminate TLS at a reverse proxy or load balancer.
- **If switched to a cloud LLM API** (e.g., OpenAI, Anthropic): ensure the API connection uses TLS and that a BAA is in place with the provider (see Section 7). Any PHI in queries would transit to their servers.

### 4.5 Transmission Security (164.312(e)) -- REQUIRED (if networked)

**Required actions (if deploying beyond local REPL):**
- All network communication must use TLS 1.2 or higher.
- If the Chroma vector store is deployed as a client-server (Chroma server mode), the connection must be encrypted.
- If model weights are downloaded from Hugging Face Hub at runtime, ensure HTTPS is used (it is by default).

---

## 5. Privacy Rule Considerations (45 CFR 164.500-534)

### 5.1 Minimum Necessary Standard (164.502(b))

**Required actions:**
- Configure the retriever to return only the minimum necessary context chunks. The current default `k=8` should be evaluated -- returning fewer chunks reduces the PHI exposure surface if PHI somehow enters the corpus.
- The metadata filter capability (`--filter-source`, `--filter-manual`, `--filter-jurisdiction`) supports minimum necessary by scoping retrieval.
- If the system is integrated with patient records in the future, implement strict minimum-necessary filters to retrieve only policy information relevant to the specific clinical scenario, without pulling in other patients' data.

### 5.2 Use and Disclosure Limitations

**Required actions:**
- Define and document the permitted uses: this system is for Medicare policy research and RCM support only.
- Prohibit use for clinical decision-making without professional review.
- The system prompt already includes a disclaimer (*"This is not legal or medical advice"*); ensure this is prominently displayed in any UI.

### 5.3 Patient Rights

**Required actions:**
- If queries containing PHI are logged, patients may have a right to access those records under 164.524.
- Maintain an accounting of disclosures if PHI is involved.
- Establish a process for handling patient access requests that may involve this system's logs.

---

## 6. Breach Notification (45 CFR 164.400-414)

### 6.1 Breach Risk Assessment

**Required actions:**
- Define what constitutes a breach for this system:
  - Unauthorized access to query logs containing PHI.
  - Unauthorized access to the system by a non-workforce member.
  - Exfiltration of the vector store (low risk since corpus is public data, but if PHI has entered the system through queries or future integrations, this changes).
  - Compromise of the LLM model leading to PHI disclosure.
- Include this system in the organization's breach notification procedures.

### 6.2 Breach Notification Procedures

**Required actions:**
- Notification to affected individuals within 60 days of discovery.
- Notification to HHS.
- Notification to media if breach affects 500+ individuals.
- Document the 4-factor risk assessment for determining breach vs. non-breach.

---

## 7. Business Associate Agreements

### 7.1 Current State (Local Deployment)

With the current architecture (local LLM, local ChromaDB, local file storage), there are **no third-party services processing ePHI**, so BAAs are limited to infrastructure:

| Component | BAA Needed? | Notes |
| --- | --- | --- |
| Hugging Face (model download) | No | Model weights are downloaded once; no PHI is sent to Hugging Face. |
| ChromaDB (local) | No | Runs locally; no data leaves the system. |
| Cloud infrastructure provider | Yes | If hosted on AWS, Azure, GCP, etc. -- BAA required. |
| Workstation vendor | No | Typically covered under device purchase/lease. |

### 7.2 If Architecture Changes

| Change | BAA Required With |
| --- | --- |
| Switch to OpenAI/Anthropic API for generation | Yes -- the LLM provider (PHI in queries is sent to their API). |
| Switch to hosted ChromaDB (Chroma Cloud) | Yes -- vector store provider. |
| Add Streamlit Cloud or similar hosted UI | Yes -- UI hosting provider. |
| Use managed embeddings API (OpenAI, Cohere) | Yes -- embeddings provider (query text is sent for embedding). |
| Cloud deployment (AWS, Azure, GCP) | Yes -- cloud provider. |

---

## 8. Implementation Checklist

### Priority 1: Must-Have Before Any Corporate Use

- [ ] **Risk analysis** -- Formal risk assessment documented and approved.
- [ ] **Access controls** -- Unique user accounts, filesystem permissions on `data/` directories (`chmod 700`, dedicated service account).
- [ ] **Audit logging** -- Implement structured query logging with timestamps and user IDs.
- [ ] **PHI-in-query mitigation** -- Add a warning banner to the query interface reminding users not to include PHI. Consider input sanitization or PHI detection.
- [ ] **Disable or encrypt query history** -- Either disable readline history persistence (`scripts/query.py`) or encrypt the history file. Disabling is simplest: remove or guard the `readline.write_history_file` call.
- [ ] **Encryption at rest** -- Full-disk encryption on all systems hosting the application.
- [ ] **Security awareness training** -- Train all users on proper use of the system and PHI handling.
- [ ] **Policies and procedures** -- Document system-specific security policies and include in the organization's HIPAA policy manual.

### Priority 2: Required for Production Deployment

- [ ] **Authentication and authorization** -- Implement user authentication (especially if adding a web UI/API).
- [ ] **TLS encryption** -- If any network communication is involved.
- [ ] **Centralized logging** -- Forward audit logs to SIEM.
- [ ] **Integrity monitoring** -- Periodic integrity checks on corpus and vector store.
- [ ] **Incident response plan** -- System-specific incident response procedures.
- [ ] **Backup and recovery** -- Regular backups of the vector store and configuration.
- [ ] **BAAs** -- Execute with any third-party service providers.
- [ ] **Automatic session timeout** -- For web UI or API deployments.

### Priority 3: Ongoing

- [ ] **Periodic risk reassessment** -- At least annually or after significant changes.
- [ ] **Security evaluation** -- Regular audits and penetration testing.
- [ ] **Policy review** -- Annual review of all HIPAA policies related to this system.
- [ ] **Workforce training refresh** -- Annual HIPAA training that includes this system.
- [ ] **Audit log review** -- Regular review of access and query logs for anomalies.

---

## 9. Architecture Changes Required

The following concrete changes to the codebase are recommended to support HIPAA compliance:

### 9.1 Add PHI Warning to Query Interface

Add a visible warning when the REPL starts:

```python
# In scripts/query.py, add after "Medicare RAG query" banner
print("WARNING: Do not include Protected Health Information (PHI) such as")
print("patient names, dates of birth, MRNs, or SSNs in your queries.")
print("De-identify all questions before submitting.")
```

### 9.2 Disable Query History by Default

The readline history file at `~/.medicare_rag_query_history` could capture PHI. Disable it by default and require an explicit opt-in:

```python
# In scripts/query.py
ENABLE_HISTORY = os.environ.get("MEDICARE_RAG_ENABLE_HISTORY", "false").lower() == "true"
```

### 9.3 Add Audit Logging Module

Create `src/medicare_rag/audit.py` with structured logging:

```python
import logging
import json
import os
from datetime import datetime, timezone

audit_logger = logging.getLogger("medicare_rag.audit")

def log_query(user_id: str, query_length: int, num_docs: int, duration_ms: float):
    """Log a query event. Logs query length, NOT query content, to avoid capturing PHI."""
    audit_logger.info(json.dumps({
        "event": "rag_query",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id or os.environ.get("USER", "unknown"),
        "query_length": query_length,
        "num_docs_retrieved": num_docs,
        "duration_ms": round(duration_ms, 2),
    }))

def log_ingestion(user_id: str, source: str, num_documents: int, num_chunks: int):
    """Log an ingestion event."""
    audit_logger.info(json.dumps({
        "event": "ingestion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id or os.environ.get("USER", "unknown"),
        "source": source,
        "num_documents": num_documents,
        "num_chunks": num_chunks,
    }))
```

### 9.4 Add Authentication Layer (for Web/API Deployment)

If a Streamlit, Gradio, or FastAPI interface is added, implement authentication before the query endpoint:

```python
# Example: FastAPI with OAuth2
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/query")
async def query(question: str, token: str = Depends(oauth2_scheme)):
    user = verify_token(token)  # Implement with your org's identity provider
    if not user:
        raise HTTPException(status_code=401)
    # ... run RAG chain with audit logging ...
```

### 9.5 Filesystem Permissions

```bash
# Restrict data directories to the service account
chown -R medicare_rag:medicare_rag data/
chmod -R 700 data/

# Protect configuration
chmod 600 .env
```

### 9.6 Add Input Sanitization (Optional but Recommended)

Consider adding a PHI detection layer that warns users if their query appears to contain PHI patterns:

```python
import re

PHI_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',         # SSN
    r'\b\d{9}\b',                       # SSN without dashes
    r'\b[A-Z]\d{9}\b',                  # MBI (Medicare Beneficiary Identifier)
    r'\b\d{2}/\d{2}/\d{4}\b',          # Date of birth pattern
    r'\bMRN\s*[:#]?\s*\d+\b',          # Medical Record Number
]

def check_for_phi(text: str) -> list[str]:
    """Return list of PHI pattern names detected in text."""
    warnings = []
    labels = ["SSN", "SSN", "MBI", "Date (possible DOB)", "MRN"]
    for pattern, label in zip(PHI_PATTERNS, labels):
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(label)
    return warnings
```

---

## Regulatory References

| Regulation | Section | Topic |
| --- | --- | --- |
| 45 CFR 164.308 | (a)(1) | Security management process (risk analysis, risk management) |
| 45 CFR 164.308 | (a)(3) | Workforce security |
| 45 CFR 164.308 | (a)(4) | Information access management |
| 45 CFR 164.308 | (a)(5) | Security awareness and training |
| 45 CFR 164.308 | (a)(6) | Security incident procedures |
| 45 CFR 164.308 | (a)(7) | Contingency plan |
| 45 CFR 164.308 | (a)(8) | Evaluation |
| 45 CFR 164.310 | (a)-(d) | Physical safeguards |
| 45 CFR 164.312 | (a) | Access control |
| 45 CFR 164.312 | (b) | Audit controls |
| 45 CFR 164.312 | (c) | Integrity |
| 45 CFR 164.312 | (e) | Transmission security |
| 45 CFR 164.502 | (b) | Minimum necessary |
| 45 CFR 164.524 | | Individual access to PHI |
| 45 CFR 164.400-414 | | Breach notification |

---

*This document should be reviewed by the organization's HIPAA Privacy Officer and Security Officer before implementation. It is not legal advice. Consult with legal counsel specializing in healthcare regulatory compliance for your specific deployment scenario.*
