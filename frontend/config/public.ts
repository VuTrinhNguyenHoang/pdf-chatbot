function parseIntValue(value: string | undefined, fallback: number, minimum = 0): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.max(minimum, parsed) : fallback;
}

export function getPublicConfig() {
  const maxUploadFiles = parseIntValue(
    process.env.NEXT_PUBLIC_MAX_UPLOAD_FILES,
    5,
    1,
  );
  const maxUploadMb = parseIntValue(
    process.env.NEXT_PUBLIC_MAX_UPLOAD_MB,
    10,
    1,
  );

  return {
    langGraphApiUrl: process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || '',
    maxUploadFiles,
    maxUploadMb,
    maxUploadBytes: maxUploadMb * 1024 * 1024,
    knowledgePageSize: parseIntValue(
      process.env.NEXT_PUBLIC_KNOWLEDGE_PAGE_SIZE,
      10,
      1,
    ),
  };
}
