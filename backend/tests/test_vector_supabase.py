import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from backend.app.tools import SupabaseVectorTool

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class VectorSupabaseTest(unittest.TestCase):
    """
    Vector Supabase 연동 테스트 (Integration Test)

    [테스트 목적]
    - SupabaseVectorTool이 설정된 임베딩 모델(Upstage 등)을 이용해 텍스트를 벡터로 정상 변환하는지 확인합니다.
    - Supabase DB의 patents 테이블을 조회하고(SELECT), 유사도 기반 벡터 검색(RPC)이 올바르게 동작하는지 확인합니다.

    [실행 방법]
    프로젝트 루트 또는 backend 디렉토리에서 아래 명령어 중 하나를 실행합니다.
    - python -m unittest backend/tests/test_vector_supabase.py
    - pytest backend/tests/test_vector_supabase.py

    주의: 이 테스트는 실제 OpenAI/Upstage API와 Supabase API를 호출하므로, 
    정상적인 환경변수(.env) 설정이 필요합니다.
    """

    @classmethod
    def setUpClass(cls):
        # 루트 .env와 backend/.env를 로드합니다.
        load_dotenv(ROOT_DIR / ".env")
        load_dotenv(BACKEND_DIR / ".env", override=True)

        # 통합 테스트를 위한 필수 환경 변수 확인 (없을 경우 테스트 스킵)
        required_envs = [
            "OPENAI_API_KEY",
            "VECTOR_SUPABASE_URL",
            "VECTOR_SUPABASE_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_EMBEDDING_MODEL",
            "OPENAI_QUERY_EMBEDDING_MODEL",
        ]
        for env_var in required_envs:
            if not os.getenv(env_var):
                raise unittest.SkipTest(f"필수 환경 변수가 없어 테스트를 건너뜁니다: {env_var}")

        # 로컬 디버그용 SSLKEYLOGFILE이 쓰기 불가 경로를 가리키면 httpx client 생성이 실패할 수 있어 제거합니다.
        os.environ.pop("SSLKEYLOGFILE", None)

        # .env에서 OpenAI/Upstage client 설정을 읽어 client를 생성합니다.
        cls.openai_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

        # SupabaseVectorTool은 내부적으로 os.getenv("VECTOR_SUPABASE_*")를 사용하여 
        # Supabase client를 생성합니다.
        cls.tool = SupabaseVectorTool(
            openai_client=cls.openai_client,
            embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "solar-embedding-1-large-passage",
            ),
            query_embedding_model=os.getenv(
                "OPENAI_QUERY_EMBEDDING_MODEL",
                "solar-embedding-1-large-query",
            ),
            match_function=os.getenv("VECTOR_SUPABASE_MATCH_FUNCTION", "match_patents"),
        )
        cls.default_query = "자동차 추진 장치"
        print(f"\n[setUpClass] 환경변수 로딩 및 클라이언트 초기화 완료. 검색어: '{cls.default_query}'")

    def test_embed_query_returns_vector(self):
        """검색 문장이 query embedding(벡터)으로 정상 변환되는지 확인합니다."""
        print(f"\n[Test 1] 임베딩 생성 시작: '{self.default_query}'...")
        embedding = self.tool.embed_query(self.default_query)

        print(f"[Test 1] 임베딩 완료: 총 {len(embedding)}차원 반환됨. (샘플: {embedding[:3]}...)")
        self.assertIsInstance(embedding, list)
        self.assertGreater(len(embedding), 0)
        self.assertIsInstance(embedding[0], float)

    def test_select_patents_returns_rows(self):
        """patents 테이블에 대한 기본 SELECT 조회가 동작하는지 확인합니다."""
        limit = 3
        print(f"\n[Test 2] patents 테이블 기본 SELECT 조회 시작 (제한: {limit}개)...")
        patents = self.tool.select_patents(limit=limit)

        print(f"[Test 2] 조회 완료: {len(patents)}개의 데이터가 반환되었습니다.")
        self.assertIsInstance(patents, list)
        self.assertLessEqual(len(patents), limit)
        if patents:
            for i, p in enumerate(patents):
                print(f"  -> 결과 {i+1}: id={p.id}, title={p.title}")
            self.assertTrue(hasattr(patents[0], "id"))
            self.assertTrue(hasattr(patents[0], "title"))

    def test_query_returns_matches(self):
        """embedding 기반 Supabase RPC(유사도 검색)가 정상 동작하는지 확인합니다."""
        limit = 3
        print(f"\n[Test 3] 유사도 검색(RPC) 시작: 함수명 '{self.tool.match_function}', 검색어 '{self.default_query}'...")
        matches = self.tool.query(self.default_query, match_count=limit)

        print(f"[Test 3] 검색 완료: {len(matches)}개의 매칭 결과가 반환되었습니다.")
        self.assertIsInstance(matches, list)
        self.assertLessEqual(len(matches), limit)
        if matches:
            for i, m in enumerate(matches):
                similarity = f"{m.similarity:.4f}" if m.similarity is not None else "None"
                print(f"  -> 매칭 {i+1}: id={m.id}, 유사도={similarity}")
            self.assertTrue(hasattr(matches[0], "id"))
            self.assertTrue(hasattr(matches[0], "similarity"))
            self.assertTrue(hasattr(matches[0], "content"))
            self.assertTrue(hasattr(matches[0], "metadata"))


if __name__ == "__main__":
    unittest.main()
