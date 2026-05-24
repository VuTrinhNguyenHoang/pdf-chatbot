import { createClient } from '@supabase/supabase-js';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface SupabaseRow {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
}

export interface ContentEntry {
  id: string;
  content: string;
  filename: string;
  title?: string;
  page?: number;
}

export interface FileEntry {
  filename: string;
  chunks: number;
  tables: number;
  images: number;
}

export interface ContentResponse {
  files: FileEntry[];
  tables: ContentEntry[];
  images: ContentEntry[];
}

export async function GET(): Promise<NextResponse<ContentResponse | { error: string }>> {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
  }

  const supabase = createClient(url, key);
  const { data: rows, error } = await supabase
    .from('documents')
    .select('id, content, metadata');

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const filesMap = new Map<string, FileEntry>();
  const tables: ContentEntry[] = [];
  const images: ContentEntry[] = [];

  for (const row of (rows as SupabaseRow[]) ?? []) {
    const meta = row.metadata || {};
    const filename = String(meta.source_file || meta.filename || 'Unknown');
    const contentType = String(meta.content_type || 'text');

    if (!filesMap.has(filename)) {
      filesMap.set(filename, { filename, chunks: 0, tables: 0, images: 0 });
    }
    const entry = filesMap.get(filename)!;
    entry.chunks++;

    const base: ContentEntry = {
      id: row.id,
      content: row.content,
      filename,
      page: meta.page_start as number | undefined,
    };

    if (contentType === 'table') {
      entry.tables++;
      const title = meta.table_title || meta.title;
      tables.push({ ...base, title: title ? String(title) : undefined });
    } else if (contentType === 'image') {
      entry.images++;
      const title = meta.image_title || meta.title;
      images.push({ ...base, title: title ? String(title) : undefined });
    }
  }

  return NextResponse.json(
    { files: Array.from(filesMap.values()), tables, images },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
