import type { AgentConfiguration, IndexConfiguration } from '@/types/graphTypes';

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

function intEnv(name: string, minimum = 0): number | undefined {
  const value = process.env[name];
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.max(minimum, parsed) : undefined;
}

function boolEnv(name: string): boolean | undefined {
  const value = process.env[name];
  if (!value) return undefined;
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
}

export function getLangGraphClientConfig() {
  const apiKey = process.env.LANGCHAIN_API_KEY;
  return {
    apiUrl: requiredEnv('NEXT_PUBLIC_LANGGRAPH_API_URL'),
    apiKey: apiKey || undefined,
  };
}

export function getIngestionAssistantId() {
  return requiredEnv('LANGGRAPH_INGESTION_ASSISTANT_ID');
}

export function getRetrievalAssistantId() {
  return requiredEnv('LANGGRAPH_RETRIEVAL_ASSISTANT_ID');
}

export function getSupabaseConfig() {
  return {
    url: requiredEnv('SUPABASE_URL'),
    serviceRoleKey: requiredEnv('SUPABASE_SERVICE_ROLE_KEY'),
  };
}

export function getRetrievalConfig(): AgentConfiguration {
  const k = intEnv('RETRIEVAL_K', 1);
  const candidateK = intEnv('RETRIEVAL_CANDIDATE_K', 1);
  const rerank = boolEnv('RETRIEVAL_RERANK');
  const config: AgentConfiguration = { retrieverProvider: 'supabase' };

  if (process.env.CHAT_MODEL) config.queryModel = process.env.CHAT_MODEL;
  if (k) config.k = k;
  if (candidateK) config.candidateK = k ? Math.max(k, candidateK) : candidateK;
  if (rerank !== undefined) config.rerank = rerank;

  return config;
}

export function getIndexConfig(): IndexConfiguration {
  return { retrieverProvider: 'supabase' };
}
