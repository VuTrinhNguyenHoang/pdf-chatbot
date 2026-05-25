import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface SupabaseRow {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
}

const CONTENT_PAGE_SIZE = 500;

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

export interface DeleteContentResponse {
  deleted: number;
}

function createSupabaseClient(): SupabaseClient | null {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    return null;
  }

  return createClient(url, key);
}


async function fetchContentRows(supabase: SupabaseClient): Promise<SupabaseRow[]> {
  const rows: SupabaseRow[] = [];

  for (let from = 0; ; from += CONTENT_PAGE_SIZE) {
    const { data, error } = await supabase
      .from('documents')
      .select('id, content, metadata')
      .order('id', { ascending: true })
      .range(from, from + CONTENT_PAGE_SIZE - 1);

    if (error) throw new Error(error.message);

    rows.push(...((data as SupabaseRow[]) ?? []));
    if (!data || data.length < CONTENT_PAGE_SIZE) break;
  }

  return rows;
}

export async function GET(): Promise<NextResponse<ContentResponse | { error: string }>> {
  const supabase = createSupabaseClient();

  if (!supabase) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
  }

  let rows: SupabaseRow[];

  try {
    rows = await fetchContentRows(supabase);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to load content' },
      { status: 500 },
    );
  }

  const filesMap = new Map<string, FileEntry>();
  const tables: ContentEntry[] = [];
  const images: ContentEntry[] = [];

  for (const row of rows) {
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

export async function DELETE(
  request: NextRequest,
): Promise<NextResponse<DeleteContentResponse | { error: string }>> {
  const supabase = createSupabaseClient();

  if (!supabase) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
  }

  const { filename } = await request.json();

  if (!filename || typeof filename !== 'string') {
    return NextResponse.json({ error: 'Filename is required' }, { status: 400 });
  }

  const { data: rows, error: selectError } = await supabase
    .from('documents')
    .select('id, metadata');

  if (selectError) {
    return NextResponse.json({ error: selectError.message }, { status: 500 });
  }

  const ids = ((rows as Pick<SupabaseRow, 'id' | 'metadata'>[]) ?? [])
    .filter((row) => {
      const meta = row.metadata || {};
      return meta.source_file === filename || meta.filename === filename;
    })
    .map((row) => row.id);

  if (!ids.length) {
    return NextResponse.json({ deleted: 0 });
  }

  const { error: deleteError } = await supabase
    .from('documents')
    .delete()
    .in('id', ids);

  if (deleteError) {
    return NextResponse.json({ error: deleteError.message }, { status: 500 });
  }

  return NextResponse.json({ deleted: ids.length });
}
