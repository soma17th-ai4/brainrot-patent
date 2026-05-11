from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


SAMPLE_RESPONSE_PATH = Path(__file__).resolve().parents[2] / "examples" / "sample_response.json"


def _load_sample_response() -> dict[str, Any]:
    with SAMPLE_RESPONSE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def generate_patent_document(
    idea: str,
    tone: str = "serious",
    use_search: bool = True,
) -> dict[str, Any]:
    response = copy.deepcopy(_load_sample_response())
    response["input"]["idea"] = idea
    response["input"]["tone"] = tone
    response["input"]["use_search"] = use_search

    if idea and idea != "방구로 가는 자동차":
        response["document"]["title"] = f"{idea}에 관한 창작형 특허 명세서"
        response["document"]["summary"] = (
            f"본 결과물은 '{idea}'라는 아이디어를 특허 명세서 문체로 재구성한 "
            "엔터테인먼트 목적의 데모 문서이다."
        )

    return response

