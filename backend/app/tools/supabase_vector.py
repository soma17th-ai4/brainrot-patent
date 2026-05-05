from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from supabase import Client, create_client

# Supabase에 만들어둘 기본 RPC 함수 이름입니다.
# 실제 DB 함수명이 다르면 SupabaseVectorTool 생성 시 match_function으로 바꿔 넣습니다.
DEFAULT_MATCH_FUNCTION = "match_documents"
# OpenAI embedding API에 사용할 기본 모델입니다.
# Supabase vector 컬럼 차원과 같은 모델을 써야 합니다.
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(frozen=True)
class SupabaseVectorMatch:
    """Supabase vector 검색 결과 1건을 백엔드에서 쓰기 쉽게 정리한 값입니다.

    Attributes:
        id: 검색된 문서 또는 row의 식별자입니다.
        content: LLM 컨텍스트로 넘길 본문 텍스트입니다.
        similarity: vector 유사도 점수입니다. DB 함수가 안 주면 None입니다.
        metadata: 출처, 제목, 태그 같은 부가 정보입니다.
    """

    id: str
    content: str
    similarity: float | None = None
    metadata: dict[str, Any] | None = None


class SupabaseVectorTool:
    """Supabase vector store에 질의하는 도구입니다.

    기본 사용 방식은 외부에서 만든 Supabase client와 OpenAI client를 주입하는 것입니다.
    테스트나 연결 코드가 아직 적은 MVP 단계라서 별도 embedder/tool 계층 없이 이 클래스 하나에서
    embedding 생성과 Supabase RPC 호출을 처리합니다.
    """

    def __init__(
        self,
        supabase: Client,
        openai_client: OpenAI,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        match_function: str = DEFAULT_MATCH_FUNCTION,
    ) -> None:
        """Supabase vector 검색 tool을 초기화합니다.

        Args:
            supabase: .rpc(...).execute() 호출이 가능한 Supabase client입니다.
            openai_client: embedding API 호출에 사용할 OpenAI client입니다.
            embedding_model: query를 embedding으로 바꿀 때 사용할 OpenAI 모델명입니다.
            match_function: Supabase에 만들어둔 vector 검색 RPC 함수명입니다.

        Returns:
            None. 생성자는 tool 객체 상태만 저장합니다.
        """
        # Supabase RPC 호출을 담당하는 클라이언트를 저장합니다.
        self.supabase = supabase
        # OpenAI embedding API 호출을 담당하는 클라이언트를 저장합니다.
        self.openai_client = openai_client
        # query embedding에 사용할 모델명을 저장합니다.
        self.embedding_model = embedding_model
        # Supabase에서 호출할 RPC 함수명을 저장합니다.
        self.match_function = match_function

    @classmethod
    def from_env(cls) -> "SupabaseVectorTool":
        """환경변수로 SupabaseVectorTool을 생성합니다.

        Args:
            없음. `.env` 또는 실행 환경의 환경변수를 사용합니다.

        Returns:
            Supabase client와 OpenAI client가 연결된 SupabaseVectorTool 인스턴스입니다.
        """
        # Supabase 프로젝트 URL을 환경변수에서 읽습니다.
        supabase_url = _get_env("SUPABASE_URL")
        # Supabase 서버 측 호출용 service role key를 환경변수에서 읽습니다.
        supabase_key = _get_env("SUPABASE_SERVICE_ROLE_KEY")
        # OpenAI API key를 환경변수에서 읽습니다.
        openai_api_key = _get_env("OPENAI_API_KEY")
        # OpenAI 호환 API를 쓸 때 base URL을 바꿀 수 있게 optional 값으로 읽습니다.
        openai_base_url = os.getenv("OPENAI_BASE_URL") or None

        # 환경변수로 만든 client들을 생성자에 주입해서 tool을 만듭니다.
        return cls(
            supabase=create_client(supabase_url, supabase_key),
            openai_client=OpenAI(api_key=openai_api_key, base_url=openai_base_url),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            match_function=os.getenv("SUPABASE_MATCH_FUNCTION", DEFAULT_MATCH_FUNCTION),
        )

    def embed_query(self, query: str) -> list[float]:
        """자연어 검색어를 OpenAI embedding 벡터로 변환합니다.

        Args:
            query: 사용자가 입력했거나 LLM/RAG 파이프라인이 만든 검색 문장입니다.

        Returns:
            Supabase vector 컬럼과 비교할 float 배열 embedding입니다.
        """
        # OpenAI embeddings API에 query와 모델명을 넘겨 embedding을 생성합니다.
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        # OpenAI 응답에서 첫 번째 embedding 배열만 꺼내 반환합니다.
        return response.data[0].embedding

    def query(
        self,
        query: str,
        match_count: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SupabaseVectorMatch]:
        """자연어 검색어로 Supabase vector 검색을 수행합니다.

        Args:
            query: 사용자가 입력했거나 LLM/RAG 파이프라인이 만든 검색 문장입니다.
            match_count: 가져올 검색 결과 개수입니다.
            filter_metadata: Supabase RPC에 넘길 metadata 필터 조건입니다.

        Returns:
            SupabaseVectorMatch 목록입니다. 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        # 1. 자연어 query를 vector embedding으로 변환합니다.
        embedding = self.embed_query(query)

        # 2. embedding이 이미 있는 경우와 같은 경로를 타도록 내부 메서드에 위임합니다.
        return self.query_by_embedding(
            embedding=embedding,
            match_count=match_count,
            filter_metadata=filter_metadata,
        )

    def query_by_embedding(
        self,
        embedding: list[float],
        match_count: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SupabaseVectorMatch]:
        """이미 만들어진 embedding으로 Supabase vector 검색을 수행합니다.

        Args:
            embedding: Supabase vector 컬럼과 비교할 query embedding입니다.
            match_count: 가져올 검색 결과 개수입니다.
            filter_metadata: Supabase RPC에 넘길 metadata 필터 조건입니다.

        Returns:
            SupabaseVectorMatch 목록입니다. 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        # Supabase RPC 함수가 받을 파라미터를 구성합니다.
        # DB 함수 인자명이 다르면 이 dict의 key도 DB 함수에 맞춰 바꿔야 합니다.
        params = {
            "query_embedding": embedding,
            "match_count": match_count,
            "filter": filter_metadata or {},
        }

        # Supabase Postgres RPC 함수를 호출하고 execute()로 실제 요청을 보냅니다.
        response = self.supabase.rpc(self.match_function, params).execute()

        # Supabase 응답의 data를 내부 표준 결과 타입으로 변환합니다.
        return [_parse_match(item) for item in response.data or []]


def _parse_match(item: dict[str, Any]) -> SupabaseVectorMatch:
    """Supabase RPC row 1개를 SupabaseVectorMatch로 변환합니다.

    Args:
        item: Supabase RPC에서 반환된 dict 한 건입니다.

    Returns:
        id, content, similarity, metadata로 정리된 SupabaseVectorMatch입니다.
    """
    return SupabaseVectorMatch(
        # id가 숫자여도 백엔드 내부에서는 문자열로 통일합니다.
        id=str(item.get("id", "")),
        # DB 컬럼명이 content면 content를 쓰고, body면 body를 대신 사용합니다.
        content=str(item.get("content") or item.get("body") or ""),
        # similarity는 DB 함수가 주는 경우에만 채워집니다.
        similarity=item.get("similarity"),
        # metadata가 없으면 None 대신 빈 dict로 맞춥니다.
        metadata=item.get("metadata") or {},
    )


def _get_env(name: str) -> str:
    """필수 환경변수를 읽고, 없으면 명확한 에러를 발생시킵니다.

    Args:
        name: 읽을 환경변수 이름입니다.

    Returns:
        환경변수에 들어있는 문자열 값입니다.
    """
    # 환경변수 값을 읽습니다.
    value = os.getenv(name)
    # 필수 값이 비어 있으면 어떤 환경변수가 빠졌는지 바로 알 수 있게 에러를 냅니다.
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    # 비어 있지 않은 환경변수 값을 반환합니다.
    return value
