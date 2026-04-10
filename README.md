# PDF Chatbot

Chatbot hỏi đáp trên tài liệu PDF.

## Thành phần chính

- `frontend/`: Next.js UI để upload PDF và chat
- `backend/`: Python LangGraph với 2 graph:
  - `ingestion_graph`: ingest tài liệu vào Supabase
  - `retrieval_graph`: retrieve ngữ cảnh và sinh câu trả lời
- `Supabase`: vector store
- `OpenAI`: chat model và embedding model

## Yêu cầu

- Python `3.11+`
- Node.js `18+`
- Yarn `1.x`
- Supabase project mới
- OpenAI API key
- LangSmith API key

## Link cần dùng

- Supabase dashboard: https://supabase.com/dashboard
- Supabase API keys: https://supabase.com/docs/guides/api/api-keys
- OpenAI platform: https://platform.openai.com/
- OpenAI API key: https://help.openai.com/en/articles/4936850-how-to-create-and-use-an-api-key
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- LangSmith: https://smith.langchain.com/
- LangSmith API key: https://docs.langchain.com/langsmith/create-account-api-key

## 1. Tạo file môi trường

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

`backend/.env`

```env
OPENAI_API_KEY=your-openai-api-key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=pdf-chatbot
```

`frontend/.env`

```env
NEXT_PUBLIC_LANGGRAPH_API_URL=http://localhost:2024
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGGRAPH_INGESTION_ASSISTANT_ID=ingestion_graph
LANGGRAPH_RETRIEVAL_ASSISTANT_ID=retrieval_graph

LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=pdf-chatbot
```

## 2. Tạo schema Supabase

Vào `SQL Editor` của Supabase và chạy:

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

## 3. Cài dependencies

Từ root project:

```bash
yarn install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 4. Chạy project

Terminal 1:

```bash
source .venv/bin/activate
cd backend
langgraph dev
```

Terminal 2:

```bash
cd frontend
yarn dev
```

Địa chỉ:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:2024`

## 5. Cách dùng

1. Mở `http://localhost:3000`
2. Upload PDF bằng nút kẹp giấy
3. Chờ ingest xong
4. Đặt câu hỏi trong ô chat
5. Mở LangGraph Studio từ link terminal `langgraph dev` nếu cần debug

## Lưu ý

- App hiện chỉ hỗ trợ `PDF`
- Tối đa `5` file mỗi lượt upload
- Mỗi file tối đa `10MB`
- Embedding hiện dùng `text-embedding-3-small`, nên Supabase phải là `vector(1536)`
- `langgraph dev` yêu cầu Python `3.11+`
- Trên Ubuntu, nếu `yarn --version` ra `0.32+git` thì bạn đang dùng `cmdtest`, không phải Yarn thật
