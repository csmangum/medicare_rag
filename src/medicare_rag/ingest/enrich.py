"""Semantic enrichment for HCPCS and ICD-10-CM code documents.

Prepends category labels, synonyms, and related terms to code document text
so that embedding models produce vectors closer to natural-language queries
(e.g. "durable medical equipment" matches HCPCS E-codes).
"""

import re

# ---------------------------------------------------------------------------
# HCPCS Level II code-prefix -> (category_label, [synonyms / related terms])
# ---------------------------------------------------------------------------
# The first letter of a HCPCS Level II code determines its broad category.
# Sub-ranges within a letter further narrow the category (e.g. A0 = ambulance,
# A4-A8 = supplies).  We match the most specific sub-range first.

_HCPCS_SUBRANGES: list[tuple[str, str, str, list[str]]] = [
    # (prefix_start, prefix_end_inclusive, label, related_terms)
    # A-codes sub-ranges
    ("A0", "A0", "Transportation and Ambulance Services",
     ["ambulance", "transport", "emergency medical transport",
      "non-emergency transport", "paramedic", "BLS", "ALS"]),
    ("A1", "A3", "Medical and Surgical Supplies",
     ["wound care", "dressing", "bandage", "surgical supply",
      "catheter", "medical supply", "gauze", "tape"]),
    ("A4", "A8", "Medical and Surgical Supplies",
     ["medical supply", "surgical supply", "ostomy", "urological supply",
      "diabetic supply", "radiopharmaceutical", "miscellaneous supply",
      "test strip", "syringe", "needle"]),
    ("A9", "A9", "Administrative and Miscellaneous",
     ["administrative", "non-covered item", "miscellaneous service"]),
    # B-codes
    ("B4", "B9", "Enteral and Parenteral Therapy",
     ["enteral nutrition", "parenteral nutrition", "tube feeding",
      "IV nutrition", "nutritional supplement", "feeding supply",
      "infusion pump", "total parenteral nutrition", "TPN"]),
    # C-codes
    ("C1", "C9", "Outpatient PPS and Temporary Hospital Codes",
     ["outpatient", "hospital outpatient", "device", "new technology",
      "pass-through", "brachytherapy", "drug", "biological", "implant"]),
    # D-codes
    ("D0", "D9", "Dental Procedures",
     ["dental", "oral surgery", "orthodontics", "prosthodontics",
      "endodontics", "periodontics", "dental implant", "tooth"]),
    # E-codes
    ("E0", "E8", "Durable Medical Equipment",
     ["durable medical equipment", "DME", "wheelchair", "hospital bed",
      "oxygen equipment", "CPAP", "BiPAP", "walker", "cane", "crutch",
      "commode", "nebulizer", "suction pump", "traction equipment",
      "patient lift", "mobility device", "power wheelchair",
      "pressure reducing mattress", "heat lamp", "TENS unit"]),
    # G-codes
    ("G0", "G9", "Procedures and Professional Services (Temporary)",
     ["professional service", "screening", "telehealth", "quality measure",
      "care management", "colorectal cancer screening", "prostate screening",
      "mammography", "EKG", "cardiovascular monitoring", "physician service"]),
    # H-codes
    ("H0", "H2", "Alcohol and Drug Abuse Treatment Services",
     ["behavioral health", "substance abuse", "alcohol treatment",
      "drug treatment", "mental health", "counseling", "rehabilitation",
      "crisis intervention", "detoxification"]),
    # J-codes
    ("J0", "J8", "Drugs Administered Other Than Oral Method",
     ["injectable drug", "infusion", "injection", "chemotherapy drug",
      "immunosuppressive drug", "inhalation solution", "immunotherapy",
      "medication administration", "IV drug", "intramuscular",
      "subcutaneous injection", "antibiotic injection"]),
    ("J9", "J9", "Chemotherapy Drugs",
     ["chemotherapy", "antineoplastic", "cancer drug", "oncology drug",
      "chemotherapy administration", "infusion therapy", "cancer treatment"]),
    # K-codes
    ("K0", "K9", "Durable Medical Equipment (Temporary)",
     ["durable medical equipment", "DME", "wheelchair", "power wheelchair",
      "wheelchair accessory", "speech generating device", "temporary DME code"]),
    # L-codes
    ("L0", "L4", "Orthotic Procedures and Devices",
     ["orthotic", "orthosis", "brace", "spinal orthosis", "cervical collar",
      "knee brace", "ankle brace", "foot orthosis", "AFO", "KAFO", "TLSO"]),
    ("L5", "L9", "Prosthetic Procedures and Devices",
     ["prosthetic", "prosthesis", "artificial limb", "upper extremity prosthesis",
      "lower extremity prosthesis", "breast prosthesis", "eye prosthesis",
      "implant", "repair", "replacement"]),
    # M-codes
    ("M0", "M0", "Medical Services",
     ["office visit", "cellular therapy", "prolotherapy",
      "intragastric hypothermia", "medical service"]),
    # P-codes
    ("P0", "P9", "Pathology and Laboratory Services",
     ["pathology", "laboratory", "lab test", "blood bank", "culture",
      "screening", "Pap smear", "cytopathology", "blood product",
      "cryoprecipitate", "platelet", "plasma"]),
    # Q-codes
    ("Q0", "Q9", "Temporary Codes",
     ["temporary code", "cast supply", "hospice care", "drug",
      "diagnostic imaging", "clinical trial", "telehealth",
      "miscellaneous service", "skin substitute"]),
    # R-codes
    ("R0", "R5", "Diagnostic Radiology Services",
     ["radiology", "X-ray", "imaging", "portable X-ray",
      "transportation of portable equipment", "diagnostic radiology"]),
    # S-codes
    ("S0", "S9", "Temporary National Codes (Non-Medicare)",
     ["non-Medicare", "private payer", "Medicaid", "nursing service",
      "home infusion therapy", "emergency transport", "genetic testing",
      "infertility treatment", "oral drug"]),
    # T-codes
    ("T1", "T5", "National T Codes (Medicaid)",
     ["Medicaid", "state plan", "nursing service", "home health aide",
      "respite care", "personal care", "private duty nursing",
      "substance abuse treatment"]),
    # V-codes
    ("V0", "V2", "Vision Services",
     ["vision", "eye exam", "eyeglasses", "contact lens", "spectacle lens",
      "low vision aid", "intraocular lens", "prosthetic eye"]),
    ("V5", "V5", "Hearing and Speech-Language Services",
     ["hearing", "hearing aid", "audiometry", "speech therapy",
      "speech-language pathology", "cochlear implant",
      "assistive listening device"]),
]

# Fallback by single letter when no sub-range matches
_HCPCS_LETTER_FALLBACK: dict[str, tuple[str, list[str]]] = {
    "A": ("Transportation, Medical and Surgical Supplies",
          ["ambulance", "transport", "medical supply", "surgical supply"]),
    "B": ("Enteral and Parenteral Therapy",
          ["enteral nutrition", "parenteral nutrition", "tube feeding"]),
    "C": ("Outpatient PPS Codes",
          ["outpatient", "hospital", "new technology"]),
    "D": ("Dental Procedures",
          ["dental", "oral surgery"]),
    "E": ("Durable Medical Equipment",
          ["DME", "wheelchair", "hospital bed", "oxygen"]),
    "G": ("Procedures and Professional Services",
          ["professional service", "screening", "telehealth"]),
    "H": ("Behavioral Health Services",
          ["behavioral health", "substance abuse", "mental health"]),
    "J": ("Drugs Administered Other Than Oral Method",
          ["injectable drug", "infusion", "chemotherapy"]),
    "K": ("Durable Medical Equipment (Temporary)",
          ["DME", "wheelchair", "power wheelchair"]),
    "L": ("Orthotics and Prosthetics",
          ["orthotic", "prosthetic", "brace", "artificial limb"]),
    "M": ("Medical Services",
          ["office visit", "medical service"]),
    "P": ("Pathology and Laboratory Services",
          ["pathology", "laboratory", "lab test"]),
    "Q": ("Temporary Codes",
          ["temporary code", "miscellaneous service"]),
    "R": ("Diagnostic Radiology Services",
          ["radiology", "X-ray", "imaging"]),
    "S": ("Temporary National Codes",
          ["non-Medicare", "private payer"]),
    "T": ("National T Codes (Medicaid)",
          ["Medicaid", "state plan"]),
    "V": ("Vision, Hearing and Speech Services",
          ["vision", "hearing", "speech therapy"]),
}

# ---------------------------------------------------------------------------
# ICD-10-CM chapter ranges  (letter + numeric range)
# ---------------------------------------------------------------------------

_ICD10_CHAPTERS: list[tuple[str, str, str, list[str]]] = [
    # (code_start, code_end, chapter_label, related_terms)
    ("A00", "B99", "Certain Infectious and Parasitic Diseases",
     ["infection", "infectious disease", "parasitic disease", "bacteria",
      "virus", "tuberculosis", "sepsis", "HIV", "hepatitis",
      "sexually transmitted infection", "STI", "fungal infection"]),
    ("C00", "D49", "Neoplasms",
     ["neoplasm", "cancer", "tumor", "malignancy", "carcinoma", "sarcoma",
      "lymphoma", "leukemia", "melanoma", "benign tumor", "oncology",
      "metastasis", "malignant neoplasm"]),
    ("D50", "D89", "Diseases of the Blood and Blood-Forming Organs",
     ["blood disorder", "anemia", "coagulation disorder", "hemophilia",
      "thrombocytopenia", "neutropenia", "immune disorder",
      "sickle cell", "thalassemia", "hematology"]),
    ("E00", "E89", "Endocrine, Nutritional and Metabolic Diseases",
     ["endocrine disorder", "diabetes", "thyroid disorder", "obesity",
      "malnutrition", "metabolic disorder", "hyperlipidemia",
      "electrolyte imbalance", "vitamin deficiency", "gout",
      "adrenal disorder", "pituitary disorder"]),
    ("F01", "F99", "Mental, Behavioral and Neurodevelopmental Disorders",
     ["mental disorder", "behavioral disorder", "depression", "anxiety",
      "schizophrenia", "bipolar disorder", "dementia", "ADHD", "autism",
      "substance use disorder", "PTSD", "eating disorder",
      "intellectual disability", "personality disorder"]),
    ("G00", "G99", "Diseases of the Nervous System",
     ["nervous system", "neurological disorder", "epilepsy", "migraine",
      "Parkinson disease", "multiple sclerosis", "neuropathy",
      "cerebral palsy", "Alzheimer disease", "nerve disorder",
      "sleep disorder", "carpal tunnel"]),
    ("H00", "H59", "Diseases of the Eye and Adnexa",
     ["eye disease", "ophthalmology", "cataract", "glaucoma",
      "macular degeneration", "retinal disorder", "conjunctivitis",
      "visual impairment", "blindness", "strabismus"]),
    ("H60", "H95", "Diseases of the Ear and Mastoid Process",
     ["ear disease", "hearing loss", "otitis media", "tinnitus",
      "vertigo", "mastoiditis", "cholesteatoma", "labyrinthitis",
      "audiology", "deafness"]),
    ("I00", "I99", "Diseases of the Circulatory System",
     ["cardiovascular disease", "heart disease", "hypertension",
      "heart failure", "atrial fibrillation", "coronary artery disease",
      "stroke", "cerebrovascular disease", "peripheral vascular disease",
      "deep vein thrombosis", "pulmonary embolism", "cardiomyopathy"]),
    ("J00", "J99", "Diseases of the Respiratory System",
     ["respiratory disease", "pneumonia", "asthma", "COPD",
      "chronic obstructive pulmonary disease", "bronchitis",
      "influenza", "respiratory failure", "pulmonary fibrosis",
      "sleep apnea", "lung disease", "pleural effusion"]),
    ("K00", "K95", "Diseases of the Digestive System",
     ["digestive disease", "gastrointestinal", "GERD", "Crohn disease",
      "ulcerative colitis", "liver disease", "cirrhosis", "pancreatitis",
      "gallstone", "hernia", "appendicitis", "gastritis",
      "intestinal obstruction", "diverticulitis"]),
    ("L00", "L99", "Diseases of the Skin and Subcutaneous Tissue",
     ["skin disease", "dermatology", "dermatitis", "psoriasis",
      "cellulitis", "pressure ulcer", "decubitus ulcer", "wound",
      "skin infection", "urticaria", "alopecia", "skin cancer"]),
    ("M00", "M99", "Diseases of the Musculoskeletal System",
     ["musculoskeletal", "arthritis", "osteoporosis", "back pain",
      "joint disorder", "rheumatoid arthritis", "osteoarthritis",
      "spinal stenosis", "disc herniation", "tendinitis", "bursitis",
      "fibromyalgia", "fracture", "orthopedic"]),
    ("N00", "N99", "Diseases of the Genitourinary System",
     ["genitourinary", "kidney disease", "renal failure",
      "urinary tract infection", "UTI", "chronic kidney disease",
      "nephrotic syndrome", "bladder disorder", "prostate disorder",
      "endometriosis", "infertility", "dialysis"]),
    # O9A has a letter suffix; _icd10_end_key treats it so O00-O99 and O9A are included.
    ("O00", "O9A", "Pregnancy, Childbirth and the Puerperium",
     ["pregnancy", "childbirth", "obstetric", "prenatal", "postpartum",
      "ectopic pregnancy", "miscarriage", "preeclampsia",
      "gestational diabetes", "cesarean section", "labor",
      "delivery complication"]),
    ("P00", "P96", "Certain Conditions Originating in the Perinatal Period",
     ["perinatal", "neonatal", "newborn", "preterm birth",
      "low birth weight", "birth injury", "neonatal jaundice",
      "respiratory distress syndrome", "fetal distress"]),
    ("Q00", "Q99", "Congenital Malformations and Chromosomal Abnormalities",
     ["congenital", "birth defect", "chromosomal abnormality",
      "Down syndrome", "cleft palate", "spina bifida",
      "congenital heart defect", "genetic disorder",
      "Turner syndrome", "malformation"]),
    ("R00", "R99", "Symptoms, Signs and Abnormal Findings",
     ["symptom", "sign", "abnormal finding", "fever", "cough",
      "chest pain", "abdominal pain", "headache", "fatigue",
      "dizziness", "nausea", "dyspnea", "shortness of breath",
      "abnormal lab result"]),
    ("S00", "T88", "Injury, Poisoning and External Causes",
     ["injury", "trauma", "fracture", "dislocation", "sprain",
      "burn", "poisoning", "adverse drug effect", "wound",
      "contusion", "laceration", "concussion",
      "foreign body", "frostbite", "complication of care"]),
    ("U00", "U85", "Codes for Special Purposes",
     ["special purpose", "emergency use", "novel organism",
      "antimicrobial resistance", "COVID-19", "SARS-CoV-2"]),
    ("V00", "Y99", "External Causes of Morbidity",
     ["external cause", "accident", "fall", "motor vehicle accident",
      "drowning", "fire", "assault", "self-harm", "poisoning",
      "adverse effect", "medical device complication"]),
    ("Z00", "Z99", "Factors Influencing Health Status",
     ["health status", "encounter", "screening", "vaccination",
      "follow-up", "family history", "personal history",
      "counseling", "health maintenance", "BMI",
      "transplant status", "long-term medication use"]),
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _hcpcs_prefix_2char(code: str) -> str:
    """Return the first two characters of a HCPCS code (e.g. 'E0' from 'E0100')."""
    return code[:2].upper() if len(code) >= 2 else code.upper()


def get_hcpcs_enrichment(code: str) -> str:
    """Return a semantic enrichment string for the given HCPCS code.

    Returns an empty string if the code prefix is not recognised.
    """
    if not code:
        return ""
    code = code.strip()
    if not code:
        return ""
    letter = code[0].upper()
    if not letter.isalpha():
        return ""

    prefix = _hcpcs_prefix_2char(code)

    for start, end, label, terms in _HCPCS_SUBRANGES:
        if start <= prefix <= end:
            terms_str = ", ".join(terms)
            return (
                f"HCPCS {letter}-codes: {label}. "
                f"Related terms: {terms_str}."
            )
    if letter in _HCPCS_LETTER_FALLBACK:
        label, terms = _HCPCS_LETTER_FALLBACK[letter]
        terms_str = ", ".join(terms)
        return (
            f"HCPCS {letter}-codes: {label}. "
            f"Related terms: {terms_str}."
        )

    return ""


def _icd10_category_key(code: str) -> tuple[str, int]:
    """Extract the ICD-10-CM category (letter + up to 2 digits) for range comparison.

    E.g. "E11.9" -> ("E", 11), "A00.0" -> ("A", 0), "O9A" -> ("O", 9).
    Only the category prefix (3 chars: 1 letter + 2 digits) is used for
    chapter-level matching; sub-category digits are ignored.
    """
    code = code.upper().replace(".", "")
    if not code:
        return ("", 0)
    letter = code[0]
    num_str = code[1:3]  # at most 2 digits after the letter
    num_match = re.match(r"(\d+)", num_str)
    num = int(num_match.group(1)) if num_match else 0
    return (letter, num)


def _icd10_end_key(end: str) -> tuple[str, int]:
    """Return the end key for a chapter range. If end has a trailing letter (e.g. O9A),
    use (letter, 99) so the full numeric block O00-O99 and the literal O9A are included.
    """
    end = end.upper().replace(".", "")
    if not end or len(end) < 2:
        return ("", 0)
    letter = end[0]
    if end[-1].isalpha() and len(end) >= 2:
        return (letter, 99)
    return _icd10_category_key(end)


def get_icd10_enrichment(code: str) -> str:
    """Return a semantic enrichment string for the given ICD-10-CM code.

    Returns an empty string if the code does not match any known chapter.
    """
    if not code or not code[0].isalpha():
        return ""

    code_key = _icd10_category_key(code)

    for start, end, label, terms in _ICD10_CHAPTERS:
        start_key = _icd10_category_key(start)
        end_key = _icd10_end_key(end)
        if start_key <= code_key <= end_key:
            terms_str = ", ".join(terms)
            return (
                f"ICD-10-CM ({start}-{end}): {label}. "
                f"Related terms: {terms_str}."
            )

    return ""


def enrich_hcpcs_text(code: str, original_text: str) -> str:
    """Prepend semantic enrichment to HCPCS document text."""
    enrichment = get_hcpcs_enrichment(code)
    if not enrichment:
        return original_text
    return f"{enrichment}\n\n{original_text}"


def enrich_icd10_text(code: str, original_text: str) -> str:
    """Prepend semantic enrichment to ICD-10-CM document text."""
    enrichment = get_icd10_enrichment(code)
    if not enrichment:
        return original_text
    return f"{enrichment}\n\n{original_text}"
