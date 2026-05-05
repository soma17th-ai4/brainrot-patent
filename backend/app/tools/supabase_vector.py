from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from supabase import Client, create_client

# Supabase에 만들어둘 기본 RPC 함수 이름입니다.
# 실제 DB 함수명이 다르면 SupabaseVectorTool 생성 시 match_function으로 바꿔 넣습니다.
DEFAULT_MATCH_FUNCTION = "match_patents"
# OpenAI embedding API에 사용할 기본 모델입니다.
# Supabase vector 컬럼 차원과 같은 모델을 써야 합니다.
DEFAULT_EMBEDDING_MODEL = "solar-embedding-1-large-passage"
# 사용자 검색 질문을 embedding할 때 사용할 기본 query 모델입니다.
DEFAULT_QUERY_EMBEDDING_MODEL = "solar-embedding-1-large-query"
# Supabase에서 조회할 전용 테이블 이름입니다.
PATENTS_TABLE = "patents"
# SELECT로 가져올 patents 테이블 컬럼 목록입니다.
PATENT_SELECT_COLUMNS = (
    "_id,"
    "applicantName,"
    "applicationDate,"
    "applicationNumber,"
    "astrtCont,"
    "bigDrawing,"
    "drawing,"
    "indexNo,"
    "inventionTitle,"
    "ipcNumber,"
    "openDate,"
    "openNumber,"
    "publicationDate,"
    "publicationNumber,"
    "registerDate,"
    "registerNumber,"
    "registerStatus,"
    "desc_v1,"
    "embedded_v2_dimensions,"
    "embedded_v2_model,"
    "embedded_v2_source_field,"
    "embedded_v2_updated_at"
)


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


@dataclass(frozen=True)
class PatentRecord:
    """patents 테이블의 SELECT 결과 1건을 담는 값입니다.

    Attributes:
        id: patents."_id" 기본키입니다.
        title: 발명의 명칭입니다. Supabase 컬럼은 "inventionTitle"입니다.
        description: 검색/RAG 본문으로 사용할 설명입니다. Supabase 컬럼은 "desc_v1"입니다.
        abstract: 초록 또는 요약 성격의 원문 필드입니다. Supabase 컬럼은 "astrtCont"입니다.
        metadata: 출원번호, 날짜, IPC 등 추가 표시나 필터링에 쓸 정보입니다.
    """

    id: str
    title: str
    description: str
    abstract: str | None = None
    metadata: dict[str, Any] | None = None


class SupabaseVectorTool:
    """Supabase vector store에 질의하는 도구입니다.

    Vector Supabase client는 VECTOR_SUPABASE_URL, VECTOR_SUPABASE_API_KEY로 직접 생성합니다.
    테스트나 연결 코드가 아직 적은 MVP 단계라서 별도 embedder/tool 계층 없이 이 클래스 하나에서
    embedding 생성과 Supabase RPC 호출을 처리합니다.
    """

    def __init__(
        self,
        openai_client: OpenAI,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        query_embedding_model: str = DEFAULT_QUERY_EMBEDDING_MODEL,
        match_function: str = DEFAULT_MATCH_FUNCTION,
        supabase: Client | None = None,
    ) -> None:
        """Supabase vector 검색 tool을 초기화합니다.

        Args:
            openai_client: embedding API 호출에 사용할 OpenAI client입니다.
            embedding_model: 문서/본문 저장용 embedding을 만들 때 사용할 모델명입니다.
            query_embedding_model: 사용자 검색 질문 embedding을 만들 때 사용할 모델명입니다.
            match_function: Supabase에 만들어둔 patents vector 검색 RPC 함수명입니다.
            supabase: 테스트에서만 선택적으로 주입할 Supabase client입니다.

        Returns:
            None. 생성자는 tool 객체 상태만 저장합니다.
        """
        # Supabase client가 주입되지 않으면 VECTOR_SUPABASE_* 환경변수로 직접 생성합니다.
        self.supabase = supabase or _create_vector_supabase_client()
        # OpenAI embedding API 호출을 담당하는 클라이언트를 저장합니다.
        self.openai_client = openai_client
        # 문서/본문 저장용 embedding에 사용할 모델명을 저장합니다.
        self.embedding_model = embedding_model
        # 사용자 검색 질문 embedding에 사용할 모델명을 저장합니다.
        self.query_embedding_model = query_embedding_model
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
        # OpenAI API key를 환경변수에서 읽습니다.
        openai_api_key = _get_env("OPENAI_API_KEY")
        # OpenAI 호환 API를 쓸 때 base URL을 바꿀 수 있게 optional 값으로 읽습니다.
        openai_base_url = os.getenv("OPENAI_BASE_URL") or None

        # OpenAI client와 모델 설정을 환경변수로 만든 뒤 tool을 생성합니다.
        # Supabase client는 생성자 내부에서 VECTOR_SUPABASE_* 환경변수로 생성됩니다.
        return cls(
            openai_client=OpenAI(api_key=openai_api_key, base_url=openai_base_url),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            query_embedding_model=os.getenv(
                "OPENAI_QUERY_EMBEDDING_MODEL",
                DEFAULT_QUERY_EMBEDDING_MODEL,
            ),
            match_function=os.getenv(
                "VECTOR_SUPABASE_MATCH_FUNCTION",
                DEFAULT_MATCH_FUNCTION,
            ),
        )

    def embed_text(self, text: str, model: str | None = None) -> list[float]:
        """문장 또는 본문을 OpenAI/Upstage embedding 벡터로 변환합니다.

        Args:
            text: embedding으로 바꿀 자연어 문장 또는 본문입니다.
            model: 사용할 embedding 모델명입니다. 없으면 저장용 passage 모델을 씁니다.

        Returns:
            Supabase vector 컬럼과 비교할 float 배열 embedding입니다.
        """
        # Upstage Solar embedding은 dimensions/encoding_format 없이 model과 input만 보냅니다.
        response = self.openai_client.embeddings.create(
            model=model or self.embedding_model,
            input=text,
        )
        # OpenAI 응답에서 첫 번째 embedding 배열만 꺼내 반환합니다.
        return response.data[0].embedding

    def embed_query(self, query: str) -> list[float]:
        """사용자 검색 질문을 query embedding 벡터로 변환합니다.

        Args:
            query: 사용자가 입력했거나 LLM/RAG 파이프라인이 만든 검색 문장입니다.

        Returns:
            patents."embedded_v2"와 비교할 4096차원 query embedding입니다.
        """
        # 검색 질문은 Solar query 모델로 embedding합니다.
        return self.embed_text(query, model=self.query_embedding_model)

    def embed_passage(self, passage: str) -> list[float]:
        """문서 본문을 저장용 passage embedding 벡터로 변환합니다.

        Args:
            passage: patents."desc_v1"처럼 문서/본문으로 저장할 텍스트입니다.

        Returns:
            patents."embedded_v2"에 저장할 4096차원 passage embedding입니다.
        """
        # 저장용 문서 본문은 Solar passage 모델로 embedding합니다.
        return self.embed_text(passage, model=self.embedding_model)

    def select_patents(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> list[PatentRecord]:
        """patents 단일 테이블에서 특허 row를 SELECT합니다.

        Args:
            limit: 가져올 row 개수입니다.
            offset: pagination을 위한 시작 위치입니다.

        Returns:
            PatentRecord 목록입니다. row가 없으면 빈 리스트를 반환합니다.
        """
        # Supabase table API로 patents 테이블만 조회합니다.
        response = (
            self.supabase.table(PATENTS_TABLE)
            .select(PATENT_SELECT_COLUMNS)
            .range(offset, offset + limit - 1)
            .execute()
        )
        # Supabase row dict를 백엔드 내부 표준 타입으로 변환합니다.
        return [_parse_patent_record(item) for item in response.data or []]

    def get_patent_by_id(self, patent_id: str) -> PatentRecord | None:
        """patents."_id"로 특허 row 1건을 SELECT합니다.

        Args:
            patent_id: patents 테이블의 "_id" 값입니다.

        Returns:
            찾으면 PatentRecord 1건을 반환하고, 없으면 None을 반환합니다.
        """
        # _id가 일치하는 row를 1건만 조회합니다.
        response = (
            self.supabase.table(PATENTS_TABLE)
            .select(PATENT_SELECT_COLUMNS)
            .eq("_id", patent_id)
            .limit(1)
            .execute()
        )
        # 결과가 없으면 None으로 명확히 반환합니다.
        if not response.data:
            return None
        # 첫 번째 row를 PatentRecord로 변환합니다.
        return _parse_patent_record(response.data[0])

    def search_patents_by_title(
        self,
        keyword: str,
        limit: int = 10,
    ) -> list[PatentRecord]:
        """발명의 명칭에 특정 키워드가 포함된 patents row를 SELECT합니다.

        Args:
            keyword: inventionTitle에서 찾을 검색어입니다.
            limit: 가져올 row 개수입니다.

        Returns:
            PatentRecord 목록입니다. 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        # inventionTitle 컬럼에서 부분 일치 검색을 수행합니다.
        response = (
            self.supabase.table(PATENTS_TABLE)
            .select(PATENT_SELECT_COLUMNS)
            .ilike("inventionTitle", f"%{keyword}%")
            .limit(limit)
            .execute()
        )
        # Supabase row dict를 백엔드 내부 표준 타입으로 변환합니다.
        return [_parse_patent_record(item) for item in response.data or []]

    def query(
        self,
        query: str,
        match_count: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SupabaseVectorMatch]:
        """자연어 검색어로 patents vector 검색을 수행합니다.

        Args:
            query: 사용자가 입력했거나 LLM/RAG 파이프라인이 만든 검색 문장입니다.
            match_count: 가져올 검색 결과 개수입니다.
            filter_metadata: Supabase RPC에 넘길 metadata 필터 조건입니다.

        Returns:
            SupabaseVectorMatch 목록입니다. 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        # 1. 자연어 query를 Solar query embedding으로 변환합니다.
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
        """이미 만들어진 embedding으로 patents vector 검색을 수행합니다.

        Args:
            embedding: patents."embedded_v2"와 비교할 query embedding입니다.
            match_count: 가져올 검색 결과 개수입니다.
            filter_metadata: Supabase RPC에 넘길 metadata 필터 조건입니다.

        Returns:
            SupabaseVectorMatch 목록입니다. 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        # Supabase RPC 함수가 받을 파라미터를 구성합니다.
        # 권장 RPC 인자명:
        # - query_embedding: 검색 query embedding입니다.
        # - match_count: 가져올 결과 개수입니다.
        # - filter: metadata 필터입니다. 지금 스키마에는 별도 JSONB metadata가 없어서 기본 빈 dict입니다.
        params = {
            "query_embedding": embedding,
            "match_count": match_count,
            "filter": filter_metadata or {},
        }

        # Supabase Postgres RPC 함수를 호출하고 execute()로 실제 vector 검색 요청을 보냅니다.
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
        # RPC 결과가 _id 또는 id 중 어떤 이름을 주더라도 문자열 id로 통일합니다.
        id=str(item.get("_id") or item.get("id", "")),
        # RAG 본문은 desc_v1을 우선 사용하고, 없으면 astrtCont/content/body 순서로 대체합니다.
        content=str(
            item.get("desc_v1")
            or item.get("astrtCont")
            or item.get("content")
            or item.get("body")
            or ""
        ),
        # similarity는 DB 함수가 주는 경우에만 채워집니다.
        similarity=item.get("similarity"),
        # patents 테이블의 주요 표시용 컬럼을 metadata로 묶습니다.
        metadata=item.get("metadata") or _build_patent_metadata(item),
    )


def _parse_patent_record(item: dict[str, Any]) -> PatentRecord:
    """Supabase patents row 1개를 PatentRecord로 변환합니다.

    Args:
        item: patents 테이블 SELECT 결과 dict 한 건입니다.

    Returns:
        id, title, description, abstract, metadata로 정리된 PatentRecord입니다.
    """
    return PatentRecord(
        # patents."_id" 기본키를 문자열로 통일합니다.
        id=str(item.get("_id", "")),
        # 발명의 명칭입니다. 없으면 빈 문자열로 반환합니다.
        title=str(item.get("inventionTitle") or ""),
        # RAG 본문으로 사용할 desc_v1입니다. 없으면 빈 문자열로 반환합니다.
        description=str(item.get("desc_v1") or ""),
        # 원본 초록/요약 필드입니다.
        abstract=item.get("astrtCont"),
        # 나머지 표시/필터용 값은 metadata로 묶습니다.
        metadata=_build_patent_metadata(item),
    )


def _build_patent_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """patents row의 부가 정보를 metadata dict로 정리합니다.

    Args:
        item: patents 테이블 SELECT 또는 RPC 결과 dict 한 건입니다.

    Returns:
        출원인, 출원번호, 등록상태, IPC, embedding 정보 등을 담은 dict입니다.
    """
    # LLM 컨텍스트나 UI 표시에서 본문과 별도로 쓸 수 있는 필드만 추립니다.
    return {
        "applicantName": item.get("applicantName"),
        "applicationDate": item.get("applicationDate"),
        "applicationNumber": item.get("applicationNumber"),
        "inventionTitle": item.get("inventionTitle"),
        "ipcNumber": item.get("ipcNumber"),
        "openDate": item.get("openDate"),
        "openNumber": item.get("openNumber"),
        "publicationDate": item.get("publicationDate"),
        "publicationNumber": item.get("publicationNumber"),
        "registerDate": item.get("registerDate"),
        "registerNumber": item.get("registerNumber"),
        "registerStatus": item.get("registerStatus"),
        "embedded_v2_dimensions": item.get("embedded_v2_dimensions"),
        "embedded_v2_model": item.get("embedded_v2_model"),
        "embedded_v2_source_field": item.get("embedded_v2_source_field"),
        "embedded_v2_updated_at": item.get("embedded_v2_updated_at"),
    }


def _create_vector_supabase_client() -> Client:
    """Vector Supabase 전용 client를 환경변수로 생성합니다.

    Args:
        없음. VECTOR_SUPABASE_URL, VECTOR_SUPABASE_API_KEY 환경변수를 사용합니다.

    Returns:
        patents 테이블과 vector RPC를 호출할 Supabase client입니다.
    """
    # Vector DB로 쓰는 Supabase 프로젝트 URL을 읽습니다.
    supabase_url = _get_env("VECTOR_SUPABASE_URL")
    # Vector DB로 쓰는 Supabase API key를 읽습니다.
    supabase_key = _get_env("VECTOR_SUPABASE_API_KEY")
    # supabase-py client를 만들어 반환합니다.
    return create_client(supabase_url, supabase_key)


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
