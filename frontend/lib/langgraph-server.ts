import { Client } from '@langchain/langgraph-sdk';
import { getLangGraphClientConfig } from '@/config/server';
import { LangGraphBase } from './langgraph-base';

// Server client singleton instance
let clientInstance: LangGraphBase | null = null;

/**
 * Creates or returns a singleton instance of the LangGraph client for server-side use
 * @returns LangGraph Client instance
 */
export const createServerClient = () => {
  if (clientInstance) {
    return clientInstance;
  }

  const config = getLangGraphClientConfig();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (config.apiKey) {
    headers['X-Api-Key'] = config.apiKey;
  }

  const client = new Client({
    apiUrl: config.apiUrl,
    defaultHeaders: headers,
  });

  clientInstance = new LangGraphBase(client);
  return clientInstance;
};

// Export all methods from the base class instance
export const langGraphServerClient = createServerClient();
