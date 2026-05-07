"use client";

import { FormEvent, useState } from "react";
import { generatePatent } from "../lib/api";
import { sampleResponse } from "../lib/sampleResponse";
import { ChatInput } from "@/components/ui/ChatInput";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { toast } from "sonner";
import { getFallback } from "@/lib/examples";
import { MessageBubble } from "@/components/ui/MessageBubble";
import { PatentResult } from "@/components/ui/PatentResult";
import { Button } from "@/components/ui/button";
import type { GenerateResponse, Tone } from "@/lib/types";

type Status = "idle" | "loading" | "done" | "error";

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [idea, setIdea] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const handleSubmit = async (
    newIdea: string,
    tone: Tone,
    useSearch: boolean,
  ) => {
    setStatus("loading");
    setErrorMsg(null);
    setResult(null);
    setIdea(newIdea);

    try {
      const res = await generatePatent({
        idea: newIdea,
        tone,
        use_search: useSearch,
      });
      setResult(res);
      setStatus("done");
    } catch (e) {
      const fallback = getFallback(newIdea);
      setResult(fallback);
      setStatus("done");
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      setErrorMsg(msg);
      toast.warning(`API 연결 실패 - 샘플 결과로 표시합니다 (${msg})`);
    }
  };

  const handleReset = () => {
    setStatus("idle");
    setIdea(null);
    setResult(null);
    setErrorMsg(null);
  };

  const handlePrint = () => {
    if (typeof window !== "undefined") window.print();
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header
        className="px-4 py-3 border-b border-border bg-card/50
no-print"
      >
        <h1 className="text-base sm:text-lg font-bold text-center">
          🧠 Brainrot Patent
        </h1>
      </header>

      <main
        className="flex-1 px-3 sm:px-4 py-4 max-w-2xl w-full mx-auto
space-y-3"
      >
        <div className="no-print">
          <Disclaimer />
        </div>

        {/* idle: 봇 인사 + 입력창 */}
        {status === "idle" && (
          <div className="no-print">
            <MessageBubble role="bot">
              황당한 아이디어를 말해줘. 진짜 특허 같은 명세서로 만들어줄게!
            </MessageBubble>
            <ChatInput onSubmit={handleSubmit} />
          </div>
        )}

        {/* idle 이후: 사용자 입력을 오른쪽 버블로 */}
        {status !== "idle" && idea && (
          <div className="no-print">
            <MessageBubble role="user">{idea}</MessageBubble>
          </div>
        )}

        {/* loading */}
        {status === "loading" && (
          <div
            className="rounded-2xl border border-border bg-card px-4 py-3
max-w-[85%] shadow-sm no-print"
          >
            <p className="text-sm text-muted-foreground animate-pulse">
              특허 문체로 변환 중...
            </p>
          </div>
        )}

        {/* 결과 카드 */}
        {result && (status === "done" || status === "error") && (
          <PatentResult
            result={result}
            onReset={handleReset}
            onPrint={handlePrint}
          />
        )}

        {/* fallback 표시 중 안내 */}
        {errorMsg && status === "done" && (
          <p className="text-xs text-muted-foreground text-center no-print">
            (백엔드 연결 실패로 샘플 데이터를 표시 중입니다)
          </p>
        )}

        {/* 극한 에러 케이스 (보통 도달 X) */}
        {status === "error" && !result && (
          <div className="text-center py-6 space-y-3 no-print">
            <p className="text-destructive">🚨 생성 중 문제가 발생했어요</p>
            <Button variant="outline" onClick={handleReset}>
              🔃 처음부터 다시
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
