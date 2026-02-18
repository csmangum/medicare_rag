"""Tests for HCPCS / ICD-10-CM semantic enrichment."""

from medicare_rag.ingest.enrich import (
    enrich_hcpcs_text,
    enrich_icd10_text,
    get_hcpcs_enrichment,
    get_icd10_enrichment,
)

# ---------------------------------------------------------------------------
# HCPCS enrichment
# ---------------------------------------------------------------------------


class TestGetHcpcsEnrichment:
    """get_hcpcs_enrichment returns meaningful labels for known code prefixes."""

    def test_a0_ambulance(self) -> None:
        result = get_hcpcs_enrichment("A0428")
        assert "Transportation" in result or "Ambulance" in result
        assert "ambulance" in result.lower()

    def test_a1_medical_supply(self) -> None:
        result = get_hcpcs_enrichment("A1001")
        assert ("Medical" in result and "Supply" in result) or ("Surgical" in result)
        assert "wound care" in result or "dressing" in result

    def test_e_codes_dme(self) -> None:
        result = get_hcpcs_enrichment("E0100")
        assert "Durable Medical Equipment" in result
        assert "wheelchair" in result
        assert "hospital bed" in result
        assert "HCPCS E-codes" in result

    def test_j0_drugs(self) -> None:
        result = get_hcpcs_enrichment("J0120")
        assert "Drug" in result
        assert "injectable drug" in result or "infusion" in result

    def test_j9_chemo(self) -> None:
        result = get_hcpcs_enrichment("J9000")
        assert "Chemotherapy" in result
        assert "antineoplastic" in result or "cancer" in result

    def test_l_orthotics(self) -> None:
        result = get_hcpcs_enrichment("L0120")
        assert "Orthotic" in result
        assert "brace" in result

    def test_l5_prosthetics(self) -> None:
        result = get_hcpcs_enrichment("L5000")
        assert "Prosthetic" in result
        assert "artificial limb" in result or "prosthesis" in result

    def test_k_dme_temporary(self) -> None:
        result = get_hcpcs_enrichment("K0001")
        assert "Durable Medical Equipment" in result
        assert "wheelchair" in result

    def test_g_codes_professional(self) -> None:
        result = get_hcpcs_enrichment("G0101")
        assert "Professional" in result or "Procedures" in result or "Service" in result

    def test_empty_code_returns_empty(self) -> None:
        assert get_hcpcs_enrichment("") == ""

    def test_numeric_code_returns_empty(self) -> None:
        assert get_hcpcs_enrichment("99213") == ""

    def test_unknown_letter_returns_empty(self) -> None:
        assert get_hcpcs_enrichment("X9999") == ""

    def test_v_vision(self) -> None:
        result = get_hcpcs_enrichment("V2020")
        assert "Vision" in result
        assert "eyeglasses" in result or "eye" in result

    def test_v5_hearing(self) -> None:
        result = get_hcpcs_enrichment("V5000")
        assert "Hearing" in result or "Speech" in result

    def test_b_enteral(self) -> None:
        result = get_hcpcs_enrichment("B4034")
        assert "Enteral" in result or "Parenteral" in result
        assert "nutrition" in result.lower()


# ---------------------------------------------------------------------------
# ICD-10-CM enrichment
# ---------------------------------------------------------------------------


class TestGetIcd10Enrichment:
    """get_icd10_enrichment returns meaningful labels for known code ranges."""

    def test_a00_infectious(self) -> None:
        result = get_icd10_enrichment("A00.0")
        assert "Infectious" in result
        assert "infection" in result

    def test_c_neoplasm(self) -> None:
        result = get_icd10_enrichment("C34.1")
        assert "Neoplasm" in result
        assert "cancer" in result

    def test_e_endocrine(self) -> None:
        result = get_icd10_enrichment("E11.9")
        assert "Endocrine" in result or "Metabolic" in result
        assert "diabetes" in result

    def test_f_mental(self) -> None:
        result = get_icd10_enrichment("F32.1")
        assert "Mental" in result
        assert "depression" in result

    def test_i_circulatory(self) -> None:
        result = get_icd10_enrichment("I10")
        assert "Circulatory" in result
        assert "hypertension" in result or "heart" in result

    def test_j_respiratory(self) -> None:
        result = get_icd10_enrichment("J44.1")
        assert "Respiratory" in result
        assert "COPD" in result or "asthma" in result

    def test_m_musculoskeletal(self) -> None:
        result = get_icd10_enrichment("M54.5")
        assert "Musculoskeletal" in result
        assert "back pain" in result or "arthritis" in result

    def test_s_injury(self) -> None:
        result = get_icd10_enrichment("S72.001A")
        assert "Injury" in result
        assert "fracture" in result

    def test_z_health_status(self) -> None:
        result = get_icd10_enrichment("Z23")
        assert "Health Status" in result or "Factors" in result
        assert "vaccination" in result or "screening" in result

    def test_empty_code_returns_empty(self) -> None:
        assert get_icd10_enrichment("") == ""

    def test_numeric_code_returns_empty(self) -> None:
        assert get_icd10_enrichment("123") == ""

    def test_d50_blood(self) -> None:
        result = get_icd10_enrichment("D50.0")
        assert "Blood" in result
        assert "anemia" in result

    def test_g_nervous(self) -> None:
        result = get_icd10_enrichment("G40.0")
        assert "Nervous" in result
        assert "epilepsy" in result or "neurological" in result

    def test_h_eye(self) -> None:
        result = get_icd10_enrichment("H25.1")
        assert "Eye" in result
        assert "cataract" in result or "ophthalmology" in result

    def test_h60_ear(self) -> None:
        result = get_icd10_enrichment("H65.0")
        assert "Ear" in result
        assert "otitis" in result or "hearing" in result

    def test_k_digestive(self) -> None:
        result = get_icd10_enrichment("K21.0")
        assert "Digestive" in result
        assert "GERD" in result or "gastrointestinal" in result

    def test_n_genitourinary(self) -> None:
        result = get_icd10_enrichment("N18.1")
        assert "Genitourinary" in result
        assert "kidney" in result

    def test_range_format(self) -> None:
        """Enrichment string includes the chapter range in parentheses."""
        result = get_icd10_enrichment("A00.0")
        assert "ICD-10-CM" in result
        assert "A00-B99" in result

    def test_o99_pregnancy_chapter(self) -> None:
        """O99 is in the pregnancy chapter (O00-O9A); enrichment uses end key so O10-O99 are included."""
        result = get_icd10_enrichment("O99.0")
        assert result != ""
        assert "Pregnancy" in result or "Puerperium" in result

    def test_o10_pregnancy_chapter(self) -> None:
        """O10 is in the pregnancy chapter (O00-O9A)."""
        result = get_icd10_enrichment("O10.0")
        assert result != ""
        assert "Pregnancy" in result or "Puerperium" in result


# ---------------------------------------------------------------------------
# enrich_*_text wrappers
# ---------------------------------------------------------------------------


class TestEnrichTextWrappers:
    """enrich_hcpcs_text / enrich_icd10_text prepend enrichment to original text."""

    def test_hcpcs_enrichment_prepended(self) -> None:
        original = "Code: E0100\n\nLong description: Cane"
        result = enrich_hcpcs_text("E0100", original)
        assert result.startswith("HCPCS E-codes")
        assert result.endswith(original)
        assert "Durable Medical Equipment" in result

    def test_icd10_enrichment_prepended(self) -> None:
        original = "Code: A00.0\n\nDescription: Cholera"
        result = enrich_icd10_text("A00.0", original)
        assert result.startswith("ICD-10-CM")
        assert result.endswith(original)
        assert "Infectious" in result

    def test_hcpcs_unknown_code_unchanged(self) -> None:
        original = "Code: X9999\n\nSomething"
        assert enrich_hcpcs_text("X9999", original) == original

    def test_icd10_empty_code_unchanged(self) -> None:
        original = "Code: \n\nNothing"
        assert enrich_icd10_text("", original) == original

    def test_enrichment_separated_by_blank_line(self) -> None:
        result = enrich_hcpcs_text("E0100", "Code: E0100")
        parts = result.split("\n\n")
        assert len(parts) >= 2
        assert parts[0].startswith("HCPCS")
        assert "Code: E0100" in parts[-1]
