import { StringToBoolean } from "class-variance-authority/types";

export type Tone = "serious" | "absurd" | "short";

export type DocumentSections = {
  title: string;
  technical_field: string;
  background: string;
  problem: string;
  configuration: string;
  claims: string[];
  summary: string;
};

export type Source = {
  title: string;
  url: string;
  snippet: string;
};

export type GenerateResponse = {
  id: string;
  status: "completed" | "error";
  input: {
    idea: string;
    tone: Tone;
    use_search: boolean;
  };
  document: DocumentSections;
  sources: Source[];
  warnings: string[];
};

export type GenerateRequest = {
  idea: string;
  tone: Tone;
  use_search: boolean;
};

//화면 표시용 한국어 라벨
export const SECTION_LABELS_KO: Record<keyof DocumentSections, string> = {
  title: "발명의 명칭",
  technical_field: "기술분야",
  background: "배경기술",
  problem: "해결하려는 과제",
  configuration: "발명의 구성",
  claims: "청구항",
  summary: "요약",
};

export const BODY_SECTION_KEYS: Array<
  Exclude<keyof DocumentSections, "title" | "claims">
> = ["technical_field", "background", "problem", "configuration", "summary"];
