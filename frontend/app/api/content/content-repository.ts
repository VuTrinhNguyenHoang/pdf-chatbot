import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { getSupabaseConfig } from '@/config/server';
import { ContentServiceError } from './content-error';

export interface ContentRow {
  id: string;
  content: string;
  metadata: Record<string, unknown> | null;
}

const CONTENT_PAGE_SIZE = 500;
const DELETE_BATCH_SIZE = 100;

export async function fetchContentRows(): Promise<ContentRow[]> {
  const supabase = createSupabaseClient();
  const rows: ContentRow[] = [];

  for (let from = 0; ; from += CONTENT_PAGE_SIZE) {
    const { data, error } = await supabase
      .from('documents')
      .select('id, content, metadata')
      .order('id', { ascending: true })
      .range(from, from + CONTENT_PAGE_SIZE - 1);

    if (error) throw new ContentServiceError(error.message);

    rows.push(...((data as ContentRow[]) ?? []));
    if (!data || data.length < CONTENT_PAGE_SIZE) break;
  }

  return rows;
}

export async function deleteRowsByFilename(filename: string): Promise<number> {
  const supabase = createSupabaseClient();
  const ids = await findDocumentIdsByFilename(supabase, filename);
  return ids.length ? deleteDocumentIds(supabase, ids) : 0;
}

function createSupabaseClient(): SupabaseClient {
  try {
    const config = getSupabaseConfig();
    return createClient(config.url, config.serviceRoleKey);
  } catch {
    throw new ContentServiceError('Supabase not configured');
  }
}

async function findDocumentIdsByFilename(
  supabase: SupabaseClient,
  filename: string,
): Promise<string[]> {
  const ids: string[] = [];

  for (let from = 0; ; from += CONTENT_PAGE_SIZE) {
    const { data, error } = await supabase
      .from('documents')
      .select('id, metadata')
      .order('id', { ascending: true })
      .range(from, from + CONTENT_PAGE_SIZE - 1);

    if (error) throw new ContentServiceError(error.message);

    const rows = (data as Pick<ContentRow, 'id' | 'metadata'>[]) ?? [];
    ids.push(
      ...rows
        .filter((row) => {
          const metadata = row.metadata || {};
          return metadata.source_file === filename || metadata.filename === filename;
        })
        .map((row) => row.id),
    );

    if (rows.length < CONTENT_PAGE_SIZE) break;
  }

  return ids;
}

async function deleteDocumentIds(
  supabase: SupabaseClient,
  ids: string[],
): Promise<number> {
  let deleted = 0;

  for (let index = 0; index < ids.length; index += DELETE_BATCH_SIZE) {
    const batch = ids.slice(index, index + DELETE_BATCH_SIZE);
    const { error } = await supabase.from('documents').delete().in('id', batch);

    if (error) throw new ContentServiceError(error.message);
    deleted += batch.length;
  }

  return deleted;
}
