import { Document } from '@langchain/core/documents';

/**
 * Represents the state of the retrieval graph / agent.
 */
export type documentType =
  | PDFDocument[]
  | { [key: string]: any }[]
  | string[]
  | string
  | 'delete';
export interface AgentState {
  query?: string;
  route?: string;
  messages: Array<{
    content: string;
    additional_kwargs: Record<string, any>;
    response_metadata: Record<string, any>;
    id: string;
    type: 'human' | 'assistant';
  }>;
  documents: documentType;
}

export interface RetrieveDocumentsNodeUpdates {
  retrieveDocuments: {
    documents: documentType;
  };
}

export interface StreamActivity {
  route: 'retrieve' | 'direct' | null;
  completedNodes: string[];
  activeNode: string | null;
  isComplete: boolean;
  error?: string;
  iterationCount?: number;  // number of checkEnough evaluations completed
}

export type PDFDocument = Document & {
  metadata?: {
    loc?: {
      lines?: { from: number; to: number };
      pageNumber?: number;
    };
    pdf?: {
      info?: {
        Title?: string;
        Creator?: string;
        Producer?: string;
        CreationDate?: string;
        IsXFAPresent?: boolean;
        PDFFormatVersion?: string;
        IsAcroFormPresent?: boolean;
      };
      version?: string;
      metadata?: unknown;
      totalPages?: number;
    };
    uuid?: string;
    source?: string;
    source_file?: string;
    filename?: string;
    content_type?: 'text' | 'table' | 'image';
    page_start?: number;
    page_end?: number;
    title?: string;
    table_title?: string;
    image_title?: string;
  };
};

export interface BaseConfiguration {
  /**
   * The vector store provider to use for retrieval.
   * @default 'supabase'
   */
  retrieverProvider?: 'supabase';

  /**
   * Additional keyword arguments to pass to the search function of the retriever for filtering.
   * @default {}
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  filterKwargs?: Record<string, any>;

  /**
   * The number of documents to return after retrieval.
   * @default 5
   */
  k?: number;

  /**
   * The number of vector-search candidates to fetch before reranking.
   * @default 12
   */
  candidateK?: number;

  /**
   * Whether to rerank vector-search candidates before answering.
   * @default false
   */
  rerank?: boolean;
}

export interface AgentConfiguration extends BaseConfiguration {
  // models
  /**
   * The language model used for processing and refining queries.
   * Should be in the form: provider/model-name.
   */
  queryModel?: string;
}

export interface IndexConfiguration extends BaseConfiguration {
}

export interface IndexSource {
  filename: string;
  mimeType: string;
  contentBase64: string;
}

export interface IndexState {
  sources?: IndexSource[];
  docs?: documentType;
}
