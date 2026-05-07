from __future__ import annotations

import os
import re
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
# 규칙 기반 검색에서 부분 일치 대상으로 삼을 patents 텍스트 컬럼입니다.
RULE_SEARCH_COLUMNS = ("inventionTitle", "astrtCont", "desc_v1")
# 한국어 조사/서술어처럼 특허 검색 키워드로 의미가 약한 짧은 표현은 제외합니다.
RULE_SEARCH_STOPWORDS = {
    "가는",
    "으로",
    "로",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "의",
    "에",
    "와",
    "과",
    "및",
    "또는",
    "하고",
    "하는",
    "하다",
    "장치",
    "방법",
    "시스템",
}


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

    def search_patents_by_rules(
        self,
        query: str,
        limit: int = 10,
        candidate_limit: int = 30,
        min_keyword_length: int = 2,
    ) -> list[PatentRecord]:
        """부분 일치와 패턴 매칭으로 patents 검색 결과를 보강합니다.

        벡터 검색은 의미적으로 가까운 결과를 잘 찾지만, 발표용처럼 짧고 황당한 한국어 입력에서는
        핵심 명사 하나가 빠질 수 있습니다. 이 메서드는 Supabase `ilike` 패턴 검색을 여러 번 수행한 뒤
        제목, 초록, 설명의 매칭 위치와 키워드 개수로 재정렬해 벡터 검색 보조 후보를 끌어올립니다.

        Args:
            query: 사용자가 입력한 검색 문장입니다.
            limit: 최종 반환할 patents row 개수입니다.
            candidate_limit: 각 패턴 검색에서 가져올 후보 row 개수입니다.
            min_keyword_length: 규칙 기반 키워드로 인정할 최소 글자 수입니다.

        Returns:
            규칙 기반 점수 순으로 정렬된 PatentRecord 목록입니다.
        """
        normalized_query = _normalize_search_text(query)
        if not normalized_query:
            return []

        # 원문 구, 공백 제거 구, 핵심 키워드를 모두 검색 패턴으로 써서 누락을 줄입니다.
        search_terms = _build_rule_search_terms(
            normalized_query,
            min_keyword_length=min_keyword_length,
        )
        if not search_terms:
            return []

        records_by_id: dict[str, PatentRecord] = {}
        scores_by_id: dict[str, float] = {}

        for term in search_terms:
            filter_value = _build_supabase_ilike_or_filter(term)
            if not filter_value:
                continue

            response = (
                self.supabase.table(PATENTS_TABLE)
                .select(PATENT_SELECT_COLUMNS)
                .or_(filter_value)
                .limit(candidate_limit)
                .execute()
            )

            for item in response.data or []:
                record = _parse_patent_record(item)
                if not record.id:
                    continue

                score = _score_rule_search_record(
                    record=record,
                    normalized_query=normalized_query,
                    search_terms=search_terms,
                    matched_term=term,
                )
                previous_score = scores_by_id.get(record.id, 0.0)
                if score <= previous_score:
                    continue

                scores_by_id[record.id] = score
                records_by_id[record.id] = _with_rule_search_metadata(record, score)

        ranked_ids = sorted(
            scores_by_id,
            key=lambda record_id: (
                -scores_by_id[record_id],
                records_by_id[record_id].title,
            ),
        )
        return [records_by_id[record_id] for record_id in ranked_ids[:limit]]

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


def _normalize_search_text(value: str | None) -> str:
    """패턴 검색과 점수 계산에 쓰기 좋게 공백과 대소문자를 정리합니다."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _build_rule_search_terms(
    query: str,
    min_keyword_length: int = 2,
) -> list[str]:
    """검색 문장에서 구 검색어와 핵심 키워드를 추출합니다."""
    terms: list[str] = []
    normalized_query = _normalize_search_text(query)
    compact_query = normalized_query.replace(" ", "")

    for candidate in (normalized_query, compact_query):
        if len(candidate) >= min_keyword_length:
            terms.append(candidate)

    tokens = re.findall(r"[0-9a-zA-Z가-힣]+", normalized_query)
    for token in tokens:
        if len(token) < min_keyword_length or token in RULE_SEARCH_STOPWORDS:
            continue
        terms.append(token)

    for left, right in zip(tokens, tokens[1:]):
        if left in RULE_SEARCH_STOPWORDS or right in RULE_SEARCH_STOPWORDS:
            continue
        combined = f"{left} {right}"
        if len(combined.replace(" ", "")) >= min_keyword_length * 2:
            terms.append(combined)

    return _dedupe_preserving_order(terms)


def _build_supabase_ilike_or_filter(term: str) -> str:
    """Supabase PostgREST `or_`에 넣을 다중 컬럼 ilike 필터 문자열을 만듭니다."""
    safe_term = _sanitize_supabase_pattern(term)
    if not safe_term:
        return ""
    pattern = f"*{safe_term}*"
    return ",".join(f"{column}.ilike.{pattern}" for column in RULE_SEARCH_COLUMNS)


def _sanitize_supabase_pattern(value: str) -> str:
    """PostgREST 필터 구문을 깨뜨릴 수 있는 문자를 제거합니다."""
    return re.sub(r"[^0-9a-zA-Z가-힣ㄱ-ㅎㅏ-ㅣ\s-]", " ", value).strip()


def _score_rule_search_record(
    record: PatentRecord,
    normalized_query: str,
    search_terms: list[str],
    matched_term: str,
) -> float:
    """패턴 검색으로 찾은 특허 row에 규칙 기반 점수를 부여합니다."""
    title = _normalize_search_text(record.title)
    abstract = _normalize_search_text(record.abstract)
    description = _normalize_search_text(record.description)
    compact_query = normalized_query.replace(" ", "")
    compact_title = title.replace(" ", "")
    score = 0.0

    if title == normalized_query:
        score += 120.0
    if normalized_query and normalized_query in title:
        score += 90.0
    if compact_query and compact_query in compact_title:
        score += 70.0
    if normalized_query and normalized_query in abstract:
        score += 45.0
    if normalized_query and normalized_query in description:
        score += 30.0

    for term in search_terms:
        compact_term = term.replace(" ", "")
        if term in title or compact_term in compact_title:
            score += 18.0
        if term in abstract:
            score += 9.0
        if term in description:
            score += 6.0

    if matched_term == normalized_query:
        score += 12.0
    elif matched_term.replace(" ", "") == compact_query:
        score += 8.0
    else:
        score += 4.0

    return score


def _with_rule_search_metadata(record: PatentRecord, score: float) -> PatentRecord:
    """규칙 기반 검색 점수를 metadata에 포함한 PatentRecord를 반환합니다."""
    metadata = dict(record.metadata or {})
    metadata["rule_search_score"] = round(score, 4)
    metadata["search_strategy"] = "rule_based_ilike"
    return PatentRecord(
        id=record.id,
        title=record.title,
        description=record.description,
        abstract=record.abstract,
        metadata=metadata,
    )


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """입력 순서를 유지하면서 중복 문자열을 제거합니다."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _normalize_search_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


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
