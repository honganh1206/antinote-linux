import { getContent } from "./noteState.svelte";

const keywords: string[] = ["todo"];

const keywordPattern = /^(\w+)(?::\s*(.*))?$/;

function parseFirstLine(content: string): {
  keyword: string;
  title: string;
} | null {
  const firstLine = content.split("\n")[0].trim();
  if (!firstLine) return null;

  const match = firstLine.match(keywordPattern);
  if (!match) return null;

  const keyword = match[1].toLowerCase();
  if (!keywords.includes(keyword)) return null;

  return { keyword, title: match[2]?.trim() ?? "" };
}

const parsed = $derived(parseFirstLine(getContent()));

export function getActiveMode(): string | null {
  return parsed?.keyword ?? null;
}

export function getKeywordTitle(): string {
  return parsed?.title ?? "";
}

export function isKeywordRegistered(keyword: string): boolean {
  return keywords.includes(keyword.toLowerCase());
}

export function getRegisteredKeywords(): string[] {
  return keywords;
}
