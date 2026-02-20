"""Tests for topic clustering (ingest/cluster.py)."""

from langchain_core.documents import Document

from medicare_rag.ingest.cluster import (
    TOPIC_DEFINITIONS,
    assign_topics,
    cluster_documents,
    get_topic_def,
    tag_documents_with_topics,
)


def _doc(content: str, source: str = "iom", doc_id: str = "d1") -> Document:
    return Document(
        page_content=content,
        metadata={"doc_id": doc_id, "source": source},
    )


class TestAssignTopics:

    def test_cardiac_rehab_detected(self):
        doc = _doc("This LCD covers cardiac rehabilitation program criteria.")
        topics = assign_topics(doc)
        assert "cardiac_rehab" in topics

    def test_cardiac_rehab_variants(self):
        for text in [
            "intensive cardiac rehab coverage",
            "cardiac rehabilitation services",
            "heart rehabilitation program",
            "cardiovascular rehab",
            "ICR program criteria",
        ]:
            assert "cardiac_rehab" in assign_topics(_doc(text)), f"Failed for: {text}"

    def test_wound_care_detected(self):
        doc = _doc("Wound care management and negative pressure wound therapy NPWT.")
        topics = assign_topics(doc)
        assert "wound_care" in topics

    def test_hyperbaric_oxygen_detected(self):
        doc = _doc("Hyperbaric oxygen therapy HBOT for diabetic wounds.")
        topics = assign_topics(doc)
        assert "hyperbaric_oxygen" in topics

    def test_dme_detected(self):
        doc = _doc("Durable medical equipment DME including wheelchairs and hospital beds.")
        topics = assign_topics(doc)
        assert "dme" in topics

    def test_physical_therapy_detected(self):
        doc = _doc("Outpatient physical therapy rehabilitation services.")
        topics = assign_topics(doc)
        assert "physical_therapy" in topics

    def test_imaging_detected(self):
        doc = _doc("Diagnostic imaging MRI and CT scan coverage criteria.")
        topics = assign_topics(doc)
        assert "imaging" in topics

    def test_home_health_detected(self):
        doc = _doc("Home health agency HHA skilled nursing services.")
        topics = assign_topics(doc)
        assert "home_health" in topics

    def test_hospice_detected(self):
        doc = _doc("Hospice palliative care for terminal illness.")
        topics = assign_topics(doc)
        assert "hospice" in topics

    def test_dialysis_detected(self):
        doc = _doc("Dialysis ESRD end-stage renal disease treatment.")
        topics = assign_topics(doc)
        assert "dialysis" in topics

    def test_chemotherapy_detected(self):
        doc = _doc("Chemotherapy oncology cancer treatment protocols.")
        topics = assign_topics(doc)
        assert "chemotherapy" in topics

    def test_mental_health_detected(self):
        doc = _doc("Mental health behavioral health psychiatric services.")
        topics = assign_topics(doc)
        assert "mental_health" in topics

    def test_ambulance_detected(self):
        doc = _doc("Ambulance emergency transport BLS ALS services.")
        topics = assign_topics(doc)
        assert "ambulance" in topics

    def test_infusion_therapy_detected(self):
        doc = _doc("Infusion therapy IV infusion drug administration.")
        topics = assign_topics(doc)
        assert "infusion_therapy" in topics

    def test_multiple_topics_assigned(self):
        doc = _doc("Cardiac rehabilitation with physical therapy exercises and MRI scan.")
        topics = assign_topics(doc)
        assert "cardiac_rehab" in topics
        assert "physical_therapy" in topics
        assert "imaging" in topics

    def test_no_topics_for_generic_text(self):
        doc = _doc("Medicare Part B covers outpatient medical services.")
        topics = assign_topics(doc)
        assert topics == []

    def test_case_insensitive(self):
        doc = _doc("CARDIAC REHABILITATION program CRITERIA")
        topics = assign_topics(doc)
        assert "cardiac_rehab" in topics

    def test_als_diagnosis_not_ambulance(self):
        """ALS (amyotrophic lateral sclerosis) should not match ambulance topic."""
        doc = _doc("ALS diagnosis and treatment coverage under Medicare.")
        topics = assign_topics(doc)
        assert "ambulance" not in topics

    def test_bureau_of_labor_statistics_not_ambulance(self):
        """BLS (Bureau of Labor Statistics) should not match ambulance topic."""
        doc = _doc("Bureau of Labor Statistics data on healthcare employment.")
        topics = assign_topics(doc)
        assert "ambulance" not in topics


class TestClusterDocuments:

    def test_groups_docs_by_topic(self):
        docs = [
            _doc("cardiac rehab coverage", doc_id="d1"),
            _doc("wound care management", doc_id="d2"),
            _doc("cardiac rehabilitation criteria", doc_id="d3"),
            _doc("generic medicare text", doc_id="d4"),
        ]
        clusters = cluster_documents(docs)
        assert "cardiac_rehab" in clusters
        assert len(clusters["cardiac_rehab"]) == 2
        assert "wound_care" in clusters
        assert len(clusters["wound_care"]) == 1
        assert "d4" not in str(clusters)

    def test_doc_in_multiple_clusters(self):
        docs = [
            _doc("cardiac rehab with wound care therapy", doc_id="d1"),
        ]
        clusters = cluster_documents(docs)
        assert "cardiac_rehab" in clusters
        assert "wound_care" in clusters
        assert clusters["cardiac_rehab"][0].metadata["doc_id"] == "d1"
        assert clusters["wound_care"][0].metadata["doc_id"] == "d1"

    def test_empty_input(self):
        assert cluster_documents([]) == {}


class TestGetTopicDef:

    def test_known_topic(self):
        td = get_topic_def("cardiac_rehab")
        assert td is not None
        assert td.label == "Cardiac Rehabilitation"

    def test_unknown_topic(self):
        assert get_topic_def("nonexistent") is None


class TestTagDocumentsWithTopics:

    def test_adds_topic_clusters_metadata(self):
        docs = [
            _doc("cardiac rehab program", doc_id="d1"),
            _doc("generic text about Medicare", doc_id="d2"),
        ]
        tagged = tag_documents_with_topics(docs)
        assert len(tagged) == 2
        assert tagged[0].metadata.get("topic_clusters") == "cardiac_rehab"
        assert "topic_clusters" not in tagged[1].metadata

    def test_multiple_topics_comma_separated(self):
        docs = [_doc("cardiac rehab with imaging MRI")]
        tagged = tag_documents_with_topics(docs)
        clusters = tagged[0].metadata.get("topic_clusters", "").split(",")
        assert "cardiac_rehab" in clusters
        assert "imaging" in clusters

    def test_does_not_mutate_original(self):
        docs = [_doc("cardiac rehab")]
        original_meta = dict(docs[0].metadata)
        tag_documents_with_topics(docs)
        assert docs[0].metadata == original_meta


class TestTopicDefinitionsCoverage:

    def test_all_definitions_have_required_fields(self):
        for td in TOPIC_DEFINITIONS:
            assert td.name, f"Missing name: {td}"
            assert td.label, f"Missing label for {td.name}"
            assert td.patterns, f"No patterns for {td.name}"
            assert td.min_pattern_matches >= 1, f"Invalid min_pattern_matches for {td.name}"

    def test_no_duplicate_names(self):
        names = [td.name for td in TOPIC_DEFINITIONS]
        assert len(names) == len(set(names))
