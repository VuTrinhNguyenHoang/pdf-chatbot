import { Client } from '@langchain/langgraph-sdk';
import { getPublicConfig } from '@/config/public';
import { LangGraphBase } from './langgraph-base';

// Frontend client singleton instance
let clientInstance: LangGraphBase | null = null;

/**
 * Creates or returns a singleton instance of the LangGraph client for frontend use
 * @returns LangGraph Client instance
 */
export const createClient = () => {
  if (clientInstance) {
    return clientInstance;
  }

  const config = getPublicConfig();

  if (!config.langGraphApiUrl) {
    throw new Error('NEXT_PUBLIC_LANGGRAPH_API_URL is not set');
  }

  const client = new Client({
    apiUrl: config.langGraphApiUrl,
  });

  clientInstance = new LangGraphBase(client);
  return clientInstance;
};

export const client = createClient();
