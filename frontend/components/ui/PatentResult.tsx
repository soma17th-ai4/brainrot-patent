import { Button } from "@/components/ui/button";
import {
  BODY_SECTION_KEYS,
  SECTION_LABELS_KO,
  type GenerateResponse,
} from "@/lib/types";

interface Props {
  result: GenerateResponse;
  onReset: () => void;
  onPrint: () => void;
}

export function PatentResult({ result, onReset, onPrint }: Props) {
  const { document, sources, warnings } = result;

  return (
    <div className="w-full">
      <article
        id="patent-doc"
        className="bg-card border-2 border-foreground/80 rounded-lg shadow-md px-5 sm:px-8 py-6"
      >
        <header className="text-center border-b-2 border-foreground/80 pb-3 mb-2">
          <p className="text-xs tracking-[0.4em] text-muted-foreground">
            특 허 명 세 서
          </p>
          <h2 className="text-lg sm:text-xl font-bold mt-1 break-keep">
            {document.title}
          </h2>
        </header>

        <div className="divide-y divide-border">
          {/*
            본문 섹션을 순회.
            summary는 마지막에 따로 그리고 싶어서 filter로 제외 후 별도 렌더.
            (그래야 청구항이 summary 직전에 배치됨 — 명세서 형식 관행)
          */}
          {BODY_SECTION_KEYS.filter((k) => k !== "summary").map((k) => (
            <section key={k} className="py-4">
              <h3 className="font-semibold text-sm sm:text-base mb-2">
                【{SECTION_LABELS_KO[k]}】
              </h3>
              <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {document[k]}
              </p>
              {/* background 섹션 바로 아래에 sources 표시 */}
              {k === "background" && sources && sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-dashed border-border">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-1">
                    참고 근거
                  </h4>
                  <ul className="space-y-1">
                    {sources.map((s, i) => (
                      <li key={i} className="text-xs text-muted-foreground">
                        [{i + 1}]{" "}
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline hover:text-foreground"
                        >
                          {s.title}
                        </a>
                        {s.snippet && (
                          <span className="block ml-4 text-[11px] text-muted-foreground/80">
                            {s.snippet}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* sources가 비었을 때의 안내 (API_CONTRACT.md 표시 규칙) */}
              {k === "background" && (!sources || sources.length === 0) && (
                <p className="mt-2 text-xs text-muted-foreground italic">
                  검색 근거 없이 생성된 데모 결과입니다.
                </p>
              )}
            </section>
          ))}

          {/* 청구항 — string 배열을 <ol><li>로 렌더 (API_CONTRACT.md "claims는 번호 목록") */}
          <section className="py-4">
            <h3 className="font-semibold text-sm sm:text-base mb-2">
              【{SECTION_LABELS_KO.claims}】
            </h3>
            <ol className="list-decimal pl-6 space-y-2 text-sm leading-relaxed">
              {document.claims.map((claim, i) => (
                <li key={i} className="break-words">
                  {claim}
                </li>
              ))}
            </ol>
          </section>

          {/* 마지막에 요약 */}
          <section className="py-4">
            <h3 className="font-semibold text-sm sm:text-base mb-2">
              【{SECTION_LABELS_KO.summary}】
            </h3>
            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
              {document.summary}
            </p>
          </section>
        </div>

        {/* 결과 하단의 면책 문구 */}
        {warnings.length > 0 && (
          <footer className="mt-4 pt-3 border-t border-border space-y-1">
            {warnings.map((w, i) => (
              <p key={i} className="text-xs text-muted-foreground">
                {w}
              </p>
            ))}
          </footer>
        )}
      </article>

      {/*
        no-print 클래스: globals.css의 @media print 규칙으로 인쇄 시 숨김.
        결과 카드만 종이에 인쇄되고 PDF/리셋 버튼은 안 들어감.
      */}
      <div className="flex flex-wrap gap-2 justify-center mt-4 no-print">
        <Button onClick={onPrint}>📄 PDF로 저장 / 인쇄</Button>
        <Button variant="outline" onClick={onReset}>
          새로 만들기
        </Button>
      </div>
    </div>
  );
}
