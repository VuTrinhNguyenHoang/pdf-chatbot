import type {
  ContentEntry,
  ContentResponse,
  DeleteContentResponse,
  FileEntry,
} from '@/types/content';
import {
  deleteRowsByFilename,
  fetchContentRows,
  type ContentRow,
} from './content-repository';

export async function listContent(): Promise<ContentResponse> {
  return groupContentRows(await fetchContentRows());
}

export async function deleteContentByFilename(
  filename: string,
): Promise<DeleteContentResponse> {
  return { deleted: await deleteRowsByFilename(filename) };
}

function groupContentRows(rows: ContentRow[]): ContentResponse {
  const filesMap = new Map<string, FileEntry>();
  const tables: ContentEntry[] = [];
  const images: ContentEntry[] = [];

  for (const row of rows) {
    const meta = row.metadata || {};
    const filename = String(meta.source_file || meta.filename || 'Unknown');
    const contentType = String(meta.content_type || 'text');
    const entry = ensureFileEntry(filesMap, filename);

    entry.chunks++;

    const base: ContentEntry = {
      id: row.id,
      content: row.content,
      filename,
      page: meta.page_start as number | undefined,
    };

    if (contentType === 'table') {
      entry.tables++;
      tables.push(tableEntry(base, meta));
    } else if (contentType === 'image') {
      entry.images++;
      images.push(imageEntry(base, meta));
    }
  }

  return { files: Array.from(filesMap.values()), tables, images };
}

function ensureFileEntry(filesMap: Map<string, FileEntry>, filename: string) {
  if (!filesMap.has(filename)) {
    filesMap.set(filename, { filename, chunks: 0, tables: 0, images: 0 });
  }
  return filesMap.get(filename)!;
}

function tableEntry(
  base: ContentEntry,
  meta: Record<string, unknown>,
): ContentEntry {
  const title = meta.table_title || meta.title;
  return { ...base, title: title ? String(title) : undefined };
}

function imageEntry(
  base: ContentEntry,
  meta: Record<string, unknown>,
): ContentEntry {
  const title = meta.image_title || meta.title;
  return {
    ...base,
    title: title ? String(title) : undefined,
    imageUrl: stringValue(meta.image_data_url),
    imageMimeType: stringValue(meta.image_mime_type),
    imageStatus: stringValue(meta.image_extraction_status),
  };
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}
