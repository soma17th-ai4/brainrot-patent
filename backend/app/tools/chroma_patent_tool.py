from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from app.storage import ChromaDBConnection, ChromaDBDocument
except ImportError:
    from backend.app.storage import ChromaDBConnection, ChromaDBDocument


DEFAULT_QUERY_EMBEDDING_MODEL = "solar-embedding-1-large-query"


@dataclass(frozen=True)
class ChromaPatentDocument:
    """migration_tmp/load_kipris_to_chroma.py가 적재한 patent 문서 1건입니다."""

    id: str
    document: str
    metadata: dict[str, Any]
    distance: float | None = None

    @property
    def mongo_id(self) -> str:
        return str(self.metadata.get("mongo_id") or self.id)

    @property
    def title(self) -> str:
        return str(self.metadata.get("inventionTitle") or "")

    @property
    def description(self) -> str:
        return str(self.metadata.get("desc_v1") or self.document)


class ChromaPatentTool:
    """마이그레이션된 ChromaDB KIPRIS collection을 조회하는 backend RAG tool입니다.

    ChromaDB 연결과 v2 REST 호출은 `backend.app.storage.chormaDB.ChromaDBConnection`에
    위임합니다. 이 tool은 patent 도메인에서 쓰기 좋은 객체와 embedding 검색 메서드만 제공합니다.
    """

    def __init__(
        self,
        db: ChromaDBConnection | None = None,
        openai_client: Any | None = None,
        query_embedding_model: str = DEFAULT_QUERY_EMBEDDING_MODEL,
    ) -> None:
        self.db = db or ChromaDBConnection.from_env()
        self.openai_client = openai_client
        self.query_embedding_model = query_embedding_model

    @classmethod
    def from_env(cls) -> "ChromaPatentTool":
        """환경변수로 ChromaPatentTool을 생성합니다."""
        from openai import OpenAI

        api_key = _get_env("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or None
        return cls(
            db=ChromaDBConnection.from_env(),
            openai_client=OpenAI(api_key=api_key, base_url=base_url),
            query_embedding_model=os.getenv(
                "OPENAI_QUERY_EMBEDDING_MODEL",
                DEFAULT_QUERY_EMBEDDING_MODEL,
            ),
        )

    def count(self) -> int:
        """현재 patent collection에 적재된 문서 수를 반환합니다."""
        return self.db.count()

    def get_by_id(self, patent_id: str) -> ChromaPatentDocument | None:
        """MongoDB `_id`와 같은 Chroma document id로 patent 1건을 조회합니다."""
        documents = self.db.get_documents(ids=[patent_id])
        return _to_patent_document(documents[0]) if documents else None

    def list_documents(
        self,
        limit: int = 10,
        offset: int = 0,
        where: dict[str, Any] | None = None,
    ) -> list[ChromaPatentDocument]:
        """patent collection 문서를 페이지 단위로 조회합니다."""
        documents = self.db.get_documents(limit=limit, offset=offset, where=where)
        return [_to_patent_document(document) for document in documents]

    def query(
        self,
        query: str,
        match_count: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[ChromaPatentDocument]:
        """자연어 query를 embedding한 뒤 patent collection에서 유사도 검색합니다."""
        embedding = self.embed_query(query)
        return self.query_by_embedding(
            embedding=embedding,
            match_count=match_count,
            where=where,
        )

    def query_by_embedding(
        self,
        embedding: list[float],
        match_count: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[ChromaPatentDocument]:
        """이미 생성된 embedding으로 patent collection 유사도 검색을 수행합니다."""
        documents = self.db.query_embeddings(
            query_embeddings=[embedding],
            n_results=match_count,
            where=where,
        )
        return [_to_patent_document(document) for document in documents]

    def embed_query(self, query: str) -> list[float]:
        """검색용 query embedding을 생성합니다."""
        if self.openai_client is None:
            raise RuntimeError("openai_client is required to embed query text")

        response = self.openai_client.embeddings.create(
            model=self.query_embedding_model,
            input=query,
        )
        return response.data[0].embedding


def _to_patent_document(document: ChromaDBDocument) -> ChromaPatentDocument:
    return ChromaPatentDocument(
        id=document.id,
        document=document.document,
        metadata=document.metadata,
        distance=document.distance,
    )


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
