from __future__ import annotations

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


KIPRIS_ADVANCED_SEARCH_URL = (
    "http://plus.kipris.or.kr/kipo-api/kipi/"
    "patUtiModInfoSearchSevice/getAdvancedSearch"
)
KIPRIS_DEFAULT_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class KiprisPatentRecord:
    """KIPRIS getAdvancedSearch 결과 특허 1건입니다."""

    index_no: str = ""
    register_status: str = ""
    invention_title: str = ""
    ipc_number: str = ""
    register_number: str = ""
    register_date: str = ""
    application_number: str = ""
    application_date: str = ""
    open_number: str = ""
    open_date: str = ""
    publication_number: str = ""
    publication_date: str = ""
    abstract: str = ""
    drawing: str = ""
    big_drawing: str = ""
    applicant_name: str = ""
    raw: dict[str, str] | None = None


@dataclass(frozen=True)
class KiprisSearchResult:
    """KIPRIS getAdvancedSearch 응답 전체를 backend에서 쓰기 쉽게 정리한 값입니다."""

    result_code: str
    result_message: str
    success: bool
    total_count: int | None
    page_no: int | None
    num_of_rows: int | None
    records: list[KiprisPatentRecord]
    raw_header: dict[str, str]
    raw_count: dict[str, str]


class KiprisTool:
    """KIPRIS 특허·실용 공개·등록공보 REST 항목별검색 도구입니다.

    현재는 `getAdvancedSearch`만 직접 호출합니다. 외부 langchain_kipris_tools 패키지를 쓰지 않고
    표준 라이브러리로 요청과 XML 파싱을 처리해 MVP backend에서 의존성 없이 사용할 수 있게 했습니다.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int = KIPRIS_DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key or os.getenv("KIPRIS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing required environment variable: KIPRIS_API_KEY")
        self.timeout_seconds = timeout_seconds

    def get_advanced_search(
        self,
        word: str = "",
        invention_title: str = "",
        astrt_cont: str = "",
        claim_scope: str = "",
        ipc_number: str = "",
        application_number: str = "",
        open_number: str = "",
        publication_number: str = "",
        register_number: str = "",
        priority_application_number: str = "",
        international_application_number: str = "",
        internation_open_number: str = "",
        application_date: str = "",
        open_date: str = "",
        publication_date: str = "",
        register_date: str = "",
        priority_application_date: str = "",
        international_application_date: str = "",
        internation_open_date: str = "",
        applicant: str = "",
        inventors: str = "",
        agent: str = "",
        right_holer: str = "",
        patent: bool = True,
        utility: bool = True,
        lastvalue: str = "",
        page_no: int = 1,
        num_of_rows: int = 30,
        sort_spec: str = "AD",
        desc_sort: bool = True,
    ) -> KiprisSearchResult:
        """KIPRIS getAdvancedSearch를 호출합니다.

        Args는 KIPRIS 문서의 입력값을 Python snake_case로 옮긴 값입니다.
        KIPRIS 원문에 오타처럼 보이는 `internationOpenNumber`, `internationOpenDate`,
        `rightHoler`는 실제 요청 파라미터명과 맞추기 위해 그대로 매핑합니다.
        """
        params = self._build_advanced_search_params(
            word=word,
            invention_title=invention_title,
            astrt_cont=astrt_cont,
            claim_scope=claim_scope,
            ipc_number=ipc_number,
            application_number=application_number,
            open_number=open_number,
            publication_number=publication_number,
            register_number=register_number,
            priority_application_number=priority_application_number,
            international_application_number=international_application_number,
            internation_open_number=internation_open_number,
            application_date=application_date,
            open_date=open_date,
            publication_date=publication_date,
            register_date=register_date,
            priority_application_date=priority_application_date,
            international_application_date=international_application_date,
            internation_open_date=internation_open_date,
            applicant=applicant,
            inventors=inventors,
            agent=agent,
            right_holer=right_holer,
            patent=patent,
            utility=utility,
            lastvalue=lastvalue,
            page_no=page_no,
            num_of_rows=num_of_rows,
            sort_spec=sort_spec,
            desc_sort=desc_sort,
        )
        xml_text = self._request_xml(KIPRIS_ADVANCED_SEARCH_URL, params)
        return _parse_advanced_search_xml(xml_text)

    def _build_advanced_search_params(self, **kwargs: Any) -> dict[str, str]:
        params = {
            "word": kwargs["word"],
            "inventionTitle": kwargs["invention_title"],
            "astrtCont": kwargs["astrt_cont"],
            "claimScope": kwargs["claim_scope"],
            "ipcNumber": kwargs["ipc_number"],
            "applicationNumber": kwargs["application_number"],
            "openNumber": kwargs["open_number"],
            "publicationNumber": kwargs["publication_number"],
            "registerNumber": kwargs["register_number"],
            "priorityApplicationNumber": kwargs["priority_application_number"],
            "internationalApplicationNumber": kwargs["international_application_number"],
            "internationOpenNumber": kwargs["internation_open_number"],
            "applicationDate": kwargs["application_date"],
            "openDate": kwargs["open_date"],
            "publicationDate": kwargs["publication_date"],
            "registerDate": kwargs["register_date"],
            "priorityApplicationDate": kwargs["priority_application_date"],
            "internationalApplicationDate": kwargs["international_application_date"],
            "internationOpenDate": kwargs["internation_open_date"],
            "applicant": kwargs["applicant"],
            "inventors": kwargs["inventors"],
            "agent": kwargs["agent"],
            "rightHoler": kwargs["right_holer"],
            "patent": _bool_to_kipris(kwargs["patent"]),
            "utility": _bool_to_kipris(kwargs["utility"]),
            "lastvalue": kwargs["lastvalue"],
            "pageNo": str(kwargs["page_no"]),
            "numOfRows": str(kwargs["num_of_rows"]),
            "sortSpec": kwargs["sort_spec"],
            "descSort": _bool_to_kipris(kwargs["desc_sort"]),
            "ServiceKey": self.api_key,
        }
        return {key: value for key, value in params.items() if value not in ("", None)}

    def _request_xml(self, url: str, params: dict[str, str]) -> str:
        query = urllib.parse.urlencode(params)
        request_url = f"{url}?{query}"
        with urllib.request.urlopen(request_url, timeout=self.timeout_seconds) as response:
            body = response.read()
        return body.decode("utf-8", errors="replace")


def _parse_advanced_search_xml(xml_text: str) -> KiprisSearchResult:
    root = ET.fromstring(xml_text)
    header = _children_text(root.find("header"))
    count = _children_text(root.find("count"))
    records = [_parse_patent_item(item) for item in root.findall(".//items/item")]
    result_code = header.get("resultCode", "")

    return KiprisSearchResult(
        result_code=result_code,
        result_message=header.get("resultMsg", ""),
        success=result_code == "00",
        total_count=_to_int_or_none(count.get("totalCount")),
        page_no=_to_int_or_none(count.get("pageNo")),
        num_of_rows=_to_int_or_none(count.get("numOfRows")),
        records=records,
        raw_header=header,
        raw_count=count,
    )


def _parse_patent_item(item: ET.Element) -> KiprisPatentRecord:
    raw = _children_text(item)
    return KiprisPatentRecord(
        index_no=raw.get("indexNo", ""),
        register_status=raw.get("registerStatus", ""),
        invention_title=raw.get("inventionTitle", ""),
        ipc_number=raw.get("ipcNumber", ""),
        register_number=raw.get("registerNumber", ""),
        register_date=raw.get("registerDate", ""),
        application_number=raw.get("applicationNumber", ""),
        application_date=raw.get("applicationDate", ""),
        open_number=raw.get("openNumber", ""),
        open_date=raw.get("openDate", ""),
        publication_number=raw.get("publicationNumber", ""),
        publication_date=raw.get("publicationDate", ""),
        abstract=raw.get("astrtCont", ""),
        drawing=raw.get("drawing", ""),
        big_drawing=raw.get("bigDrawing", ""),
        applicant_name=raw.get("applicantName", ""),
        raw=raw,
    )


def _children_text(element: ET.Element | None) -> dict[str, str]:
    if element is None:
        return {}
    return {
        child.tag: (child.text or "").strip()
        for child in list(element)
    }


def _to_int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_to_kipris(value: bool) -> str:
    return "true" if value else "false"
