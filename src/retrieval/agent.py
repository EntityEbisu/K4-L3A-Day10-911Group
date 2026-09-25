from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool

from core.config import Settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm


def build_agent(settings: Settings, index: LocalEmbeddingIndex):
    @tool
    def semantic_search_papers(query: str, top_k: int = 4) -> str:
        """Tìm kiếm ngữ nghĩa trong kho bài báo đã lập chỉ mục và trả về các bài liên quan nhất."""
        results = index.search(query, top_k=top_k)
        lines = []
        for result in results:
            lines.append(
                f"paper_id: {result.paper_id}\n"
                f"title: {result.title}\n"
                f"score: {result.score:.4f}\n"
                f"{result.content}"
            )
        return "\n\n".join(lines) or "Không tìm thấy thông tin trong kho dữ liệu đã lập chỉ mục."

    @tool
    def lookup_paper(paper_id_or_title: str) -> str:
        """Tra cứu bài báo theo paper_id hoặc tiêu đề chính xác trong kho dữ liệu cục bộ."""
        record = index.lookup(paper_id_or_title)
        if not record:
            return "Không tìm thấy thông tin trong kho dữ liệu đã lập chỉ mục."
        return (
            f"paper_id: {record['paper_id']}\n"
            f"title: {record['title']}\n"
            f"{record['content']}"
        )

    llm = build_llm(settings=settings, temperature=0.0)
    return create_agent(
        model=llm,
        tools=[semantic_search_papers, lookup_paper],
        system_prompt=(
            "Bạn trả lời bằng tiếng Việt về kho bài báo khoa học đã lập chỉ mục từ Crossref. "
            "Luôn dùng công cụ trước khi trả lời câu hỏi mang tính sự kiện. "
            "Chỉ trích dẫn sự thật lấy từ kết quả công cụ. "
            "Nếu kho dữ liệu không đủ bằng chứng, hãy nói rõ: "
            "'Không tìm thấy thông tin trong kho dữ liệu đã lập chỉ mục.'"
        ),
        name="paper_corpus_agent",
    )


def run_agent_question(agent: Any, question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))
