"""RAG chain with OpenRouter (Phase 4)."""
from typing import Any

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from medicare_rag.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)
from medicare_rag.query.retriever import get_retriever

SYSTEM_PROMPT = """You are a Medicare Revenue Cycle Management assistant. Answer the user's question using ONLY the provided context. Cite sources using [1], [2], etc. corresponding to the numbered context items. If the context is insufficient to answer, say so explicitly. This is not legal or medical advice."""

USER_PROMPT = """Context:
{context}

Question: {question}"""


def _invoke_chain(prompt: ChatPromptTemplate, llm: Any, input_dict: dict) -> Any:
    """Invoke prompt | llm. Extracted for testability."""
    return (prompt | llm).invoke(input_dict)


def _format_context(docs: list[Document]) -> str:
    return "\n\n".join(
        f"[{i + 1}] {d.page_content}" for i, d in enumerate(docs)
    )


def _create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY or "dummy",
        model=OPENROUTER_MODEL,
    )


def build_rag_chain(
    retriever: Any = None,
    k: int = 8,
    metadata_filter: dict | None = None,
):
    """Build an LCEL RAG chain. Returns a runnable that takes {"question": str} and returns {"answer": str, "source_documents": list[Document]}."""
    if retriever is None:
        retriever = get_retriever(k=k, metadata_filter=metadata_filter)
    llm = _create_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT),
        ]
    )

    def runnable_invoke(input_dict: dict) -> dict:
        question = input_dict.get("question", "")
        docs = retriever.invoke(question)
        context = _format_context(docs)
        response = _invoke_chain(prompt, llm, {"context": context, "question": question})
        content = getattr(response, "content", None)
        return {
            "answer": content if content is not None else str(response),
            "source_documents": docs,
        }

    return runnable_invoke


def run_rag(
    question: str,
    retriever: Any = None,
    k: int = 8,
    metadata_filter: dict | None = None,
) -> tuple[str, list[Document]]:
    """Run the RAG chain for one question. Returns (answer, source_documents)."""
    invoke = build_rag_chain(
        retriever=retriever,
        k=k,
        metadata_filter=metadata_filter,
    )
    result = invoke({"question": question})
    return result["answer"], result["source_documents"]
