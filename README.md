# PDF Chatbot

RAG-based PDF Q&A application. Users upload PDF documents, the backend parses and chunks them with Docling, embeddings are stored in Supabase pgvector, and users can ask questions through a streaming chat UI with source attribution.

The current app supports text, table, and image-aware ingestion, document deletion from the UI, file-level ingest progress, reranking after vector search, and a Knowledge sidebar for browsing ingested files, extracted tables, and extracted images.

## Features

- Upload and ingest PDF files from the chat UI.
- Track ingest progress per file.
- Parse PDF text, tables, and images with Docling and `HybridChunker`.
- Extract table content as markdown and preview it in the sidebar.
- Extract PDF images, store bounded preview metadata, and preview images in the sidebar.
- Generate optional image descriptions with a vision model during ingestion.
- Store chunks and embeddings in Supabase PostgreSQL with pgvector.
- Stream chat responses through Server-Sent Events.
- Return sources with content type, page range, file name, and title metadata.
- Rerank vector-search candidates before answer generation.
- Delete all chunks, tables, images, and embeddings for a file from the UI.

## Architecture

```mermaid
flowchart LR
  User["User"] --> UI["Next.js frontend"]
  UI --> IngestAPI["/api/ingest"]
  UI --> ChatAPI["/api/chat"]
  UI --> ContentAPI["/api/content"]

  IngestAPI --> IngestionGraph["LangGraph ingestion_graph"]
  ChatAPI --> RetrievalGraph["LangGraph retrieval_graph"]
  ContentAPI --> Supabase[("Supabase documents + pgvector")]

  IngestionGraph --> Docling["Docling parser"]
  Docling --> Embeddings["OpenAI embeddings"]
  Embeddings --> Supabase

  RetrievalGraph --> Supabase
  RetrievalGraph --> Reranker["LLM reranker"]
  Reranker --> Generator["LLM answer generation"]
  Generator --> UI
```

### Ingestion Flow

```mermaid
sequenceDiagram
  participant U as User
  participant F as Frontend
  participant I as ingestion_graph
  participant D as Docling
  participant O as OpenAI Embeddings/Vision
  participant S as Supabase

  U->>F: Upload PDF files
  F->>I: Send file sources
  I->>D: Parse PDF
  D-->>I: Text, table, and image items
  I->>O: Embed chunks
  I->>O: Optionally describe images
  I->>S: Insert documents with metadata and embeddings
  I-->>F: Per-file progress and completion
```

### Retrieval Flow

```mermaid
sequenceDiagram
  participant U as User
  participant F as Frontend
  participant R as retrieval_graph
  participant S as Supabase
  participant L as LLM

  U->>F: Ask a question
  F->>R: Stream query request
  R->>R: Route query
  R->>S: Vector search candidates
  R->>L: Rerank candidates
  R->>L: Generate grounded answer
  R-->>F: Stream answer tokens and sources
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| UI components | Radix UI, lucide-react |
| Backend orchestration | Python, LangGraph, LangChain, Pydantic |
| PDF parsing | Docling, HybridChunker |
| Vector database | Supabase PostgreSQL, pgvector |
| LLM | OpenAI chat model, reranking model, optional vision model |
| Embeddings | `text-embedding-3-small` |
| Streaming | Server-Sent Events |

## Repository Structure

```text
.
├── backend/
│   ├── src/ingestion_graph/
│   │   ├── graph.py              # LangGraph ingestion workflow
│   │   ├── docling_parser.py     # PDF parsing, table/image extraction
│   │   └── state.py              # Ingestion graph state types
│   ├── src/retrieval_graph/
│   │   ├── graph.py              # Retrieval, reranking, answer generation
│   │   ├── prompts.py            # System prompts
│   │   ├── rerank.py             # Candidate reranking
│   │   └── utils.py              # Retrieved document formatting
│   └── src/shared/
│       ├── retrieval.py          # Supabase vector store wrapper
│       └── utils.py              # Chat model loading
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Main chat UI
│   │   └── api/
│   │       ├── chat/route.ts     # Streaming chat endpoint
│   │       ├── ingest/route.ts   # Upload and ingestion endpoint
│   │       └── content/route.ts  # Knowledge sidebar and deletion endpoint
│   ├── components/
│   │   ├── chat-message.tsx      # Message, source, and activity rendering
│   │   └── knowledge-sidebar.tsx # Files, tables, images, deletion UI
│   ├── constants/graphConfigs.ts # LangGraph IDs and retrieval config
│   ├── lib/langgraph-base.ts     # LangGraph SDK wrapper
│   └── types/graphTypes.ts       # Shared frontend graph types
├── package.json                  # Root Yarn workspace scripts
└── README.md
```

## Prerequisites

- Python `3.11+`
- Node.js `18+`
- Yarn `1.x`
- Supabase project
- OpenAI API key
- LangSmith API key, optional but recommended for tracing

Useful links:

- [Supabase dashboard](https://supabase.com/dashboard)
- [Supabase API keys](https://supabase.com/docs/guides/api/api-keys)
- [OpenAI platform](https://platform.openai.com/)
- [OpenAI API keys](https://help.openai.com/en/articles/4936850-how-to-create-and-use-an-api-key)
- [LangSmith](https://smith.langchain.com/)

## Environment Variables

Create the env files from the examples:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### `backend/.env`

```env
OPENAI_API_KEY=your-openai-api-key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

ENABLE_IMAGE_DESCRIPTIONS=true
MAX_IMAGE_DESCRIPTIONS_PER_FILE=20
PDF_IMAGE_SCALE=2.0
PDF_IMAGE_MAX_EDGE=1400
MAX_IMAGE_PREVIEW_BYTES=1500000

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=pdf-chatbot
```

### `frontend/.env`

```env
NEXT_PUBLIC_LANGGRAPH_API_URL=http://localhost:2024
LANGGRAPH_INGESTION_ASSISTANT_ID=ingestion_graph
LANGGRAPH_RETRIEVAL_ASSISTANT_ID=retrieval_graph

SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=pdf-chatbot
```

### Variable Reference

| Variable | Required | Used by | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Backend | OpenAI API key for chat, embeddings, reranking, and optional vision descriptions. |
| `SUPABASE_URL` | Yes | Backend, Frontend API routes | Supabase project URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Backend, Frontend API routes | Server-side key for insert, list, and delete operations. Do not expose it with `NEXT_PUBLIC_`. |
| `NEXT_PUBLIC_LANGGRAPH_API_URL` | Yes | Frontend | LangGraph API URL, usually `http://localhost:2024`. |
| `LANGGRAPH_INGESTION_ASSISTANT_ID` | Yes | Frontend | LangGraph assistant ID for ingestion. |
| `LANGGRAPH_RETRIEVAL_ASSISTANT_ID` | Yes | Frontend | LangGraph assistant ID for retrieval/chat. |
| `ENABLE_IMAGE_DESCRIPTIONS` | No | Backend | Set `false` to skip vision-model image descriptions while still extracting image previews. |
| `MAX_IMAGE_DESCRIPTIONS_PER_FILE` | No | Backend | Maximum number of images per file sent to the vision model. Default: `20`. |
| `PDF_IMAGE_SCALE` | No | Backend | Docling image rendering scale. Default: `2.0`. |
| `PDF_IMAGE_MAX_EDGE` | No | Backend | Maximum edge size for stored image previews. Default: `1400`. |
| `MAX_IMAGE_PREVIEW_BYTES` | No | Backend | Maximum encoded preview bytes stored in metadata. Default: `1500000`. |
| `LANGCHAIN_TRACING_V2` | No | Backend, Frontend API routes | Enables LangSmith tracing when set to `true`. |
| `LANGCHAIN_API_KEY` | No | Backend, Frontend API routes | LangSmith API key. |
| `LANGCHAIN_PROJECT` | No | Backend, Frontend API routes | LangSmith project name. |

## Supabase Setup

Open the Supabase SQL Editor and run:

```sql
create extension if not exists vector;
create extension if not exists pgcrypto;

create table documents (
  id uuid primary key default gen_random_uuid(),
  content text,
  metadata jsonb,
  embedding vector(1536)
);

create or replace function match_documents (
  query_embedding vector(1536),
  match_count int default null,
  filter jsonb default '{}'
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  embedding jsonb,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    (documents.embedding::text)::jsonb as embedding,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

The `documents.embedding` dimension is `1536` because the default embedding model is `text-embedding-3-small`.

## Installation

From the repository root:

```bash
yarn install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Running Locally

Run the backend and frontend in separate terminals from the repository root.

Terminal 1, backend:

```bash
source .venv/bin/activate
yarn backend:dev
```

Terminal 2, frontend:

```bash
yarn frontend:dev
```

Local URLs:

- Frontend: `http://localhost:3000`
- LangGraph API: `http://localhost:2024`
- LangGraph Studio: printed by `yarn backend:dev` when available

## Usage

1. Open `http://localhost:3000`.
2. Upload PDF files with the attachment button.
3. Watch the per-file ingestion progress.
4. Use the Knowledge sidebar to inspect files, tables, and images.
5. Click a table to open its markdown table preview.
6. Click an image to open its image preview.
7. Ask questions in the chat input.
8. Inspect source cards under assistant answers.
9. Delete a file from the Knowledge sidebar when it should be removed from Supabase.

## Development Commands

```bash
# Frontend development server
yarn frontend:dev

# Backend LangGraph development server
source .venv/bin/activate
yarn backend:dev

# Frontend production build
yarn frontend:build

# TypeScript check
node node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json

# Whitespace check before committing
git diff --check
```

## Retrieval Configuration

The frontend retrieval configuration is defined in `frontend/constants/graphConfigs.ts`.

Current default behavior:

- Fetch `candidateK=12` vector-search candidates.
- Rerank candidates with an LLM.
- Keep `k=5` final documents for answer generation.

## Image Extraction Configuration

Image extraction is enabled in the parser by Docling `PdfPipelineOptions.generate_picture_images = true`.

There are three separate image-related behaviors:

1. Image detection and preview extraction from PDF.
2. Preview storage in document metadata.
3. Optional text descriptions generated by the vision model.

`ENABLE_IMAGE_DESCRIPTIONS=false` disables only the vision-model description step. It does not disable image detection or preview extraction.

Default image limits:

```env
ENABLE_IMAGE_DESCRIPTIONS=true
MAX_IMAGE_DESCRIPTIONS_PER_FILE=20
PDF_IMAGE_SCALE=2.0
PDF_IMAGE_MAX_EDGE=1400
MAX_IMAGE_PREVIEW_BYTES=1500000
```

For local testing with very high limits:

```env
ENABLE_IMAGE_DESCRIPTIONS=true
MAX_IMAGE_DESCRIPTIONS_PER_FILE=999999
MAX_IMAGE_PREVIEW_BYTES=100000000
PDF_IMAGE_MAX_EDGE=4000
PDF_IMAGE_SCALE=2.0
```

The code currently expects numeric values. It does not support `unlimited` as a literal value.

## Operational Notes

- Run commands from the repository root unless a command says otherwise.
- Activate `.venv` before running the backend because `langgraph`, Docling, LangChain, and Supabase Python dependencies are installed there.
- Keep `SUPABASE_SERVICE_ROLE_KEY` server-side only. Do not prefix it with `NEXT_PUBLIC_`.
- `frontend/.env` also needs Supabase credentials because `/api/content` lists and deletes document rows from a Next.js server route.
- The app currently accepts only PDF uploads.
- The upload endpoint rejects files larger than `10MB`.
- The current UI upload flow is designed for up to `5` files per ingest batch.
- If an image is detected but the preview is too large, the image still appears in the sidebar, but the dialog shows a fallback instead of a preview.
- If no images appear for a PDF, Docling likely did not classify any element as a `PictureItem` for that file.
- Browserlist warnings during frontend build are informational and do not block the build.

## Current Limitations

- No authentication or per-user document isolation. All sessions share the same Supabase `documents` table.
- Chat thread history is not persisted after page refresh.
- Image previews are stored in metadata with a size cap. A production setup should move large previews to object storage.
- There is no automated browser screenshot test suite yet.
- Retrieval filtering is available through metadata but there is no full user-facing filter UI yet.

## Suggested Improvements

- Add authentication and per-user document ownership.
- Store image previews in Supabase Storage instead of JSONB metadata.
- Add Playwright E2E tests for upload, delete, table preview, image preview, and chat streaming.
- Persist chat threads and message history.
- Add document-level metadata filters in the chat UI.
- Add RAG evaluation datasets and regression checks.
