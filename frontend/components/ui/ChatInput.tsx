"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { SAMPLE_IDEAS } from "@/lib/examples";
import type { Tone } from "@/lib/types";

const TONE_OPTIONS: { value: Tone; label: string }[] = [
  { value: "serious", label: "🎓 진 지 하 게" },
  { value: "absurd", label: "🌀 황 당 하 게" },
  { value: "short", label: "✂️ 짧 게" },
];

interface Props {
  onSubmit: (idea: string, tone: Tone, useSearch: boolean) => void;
  disabled?: boolean;
}

export function ChatInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");
  const [tone, setTone] = useState<Tone>("serious");
  const [useSearch, setUseSearch] = useState(true);

  const submit = (idea: string) => {
    const v = idea.trim();
    if (!v || disabled) return;
    onSubmit(v, tone, useSearch);
    setValue("");
  };

  return (
    <div className="space-y-3">
      {/* 시연용 빠른 버튼 3개 */}
      <div className="flex flex-wrap gap-2">
        {SAMPLE_IDEAS.map((ex) => (
          <Button
            key={ex}
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => submit(ex)}
          >
            {ex}
          </Button>
        ))}
      </div>

      <Textarea
        placeholder="황당한 아이디어를 입력하세요 (예: 방구로 가는 자동차)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={3}
        disabled={disabled}
        maxLength={200}
        className="resize-none"
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">톤 :</Label>
          <div className="flex gap-1">
            {TONE_OPTIONS.map((opt) => (
              <Button
                key={opt.value}
                type="button"
                variant={tone === opt.value ? "default" : "outline"}
                size="sm"
                disabled={disabled}
                onClick={() => setTone(opt.value)}
                className="text-xs"
              >
                {opt.label}
              </Button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={useSearch}
            onChange={(e) => setUseSearch(e.target.checked)}
            disabled={disabled}
            className="accent-primary"
          />
          검색 근거 사용
        </label>

        <Button
          onClick={() => submit(value)}
          disabled={disabled || !value.trim()}
          className="ml-auto"
        >
          명세서 생성
        </Button>
      </div>
    </div>
  );
}
