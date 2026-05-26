import { NextResponse, type NextRequest } from 'next/server';
import {
  deleteContentByFilename,
  listContent,
} from './content-service';
import { ContentServiceError } from './content-error';
import type { ContentResponse, DeleteContentResponse } from '@/types/content';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type ErrorResponse = { error: string };

export async function GET(): Promise<NextResponse<ContentResponse | ErrorResponse>> {
  try {
    return NextResponse.json(await listContent(), {
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch (error) {
    return contentErrorResponse(error, 'Failed to load content');
  }
}

export async function DELETE(
  request: NextRequest,
): Promise<NextResponse<DeleteContentResponse | ErrorResponse>> {
  const payload = await request.json() as { filename?: unknown };

  if (!payload.filename || typeof payload.filename !== 'string') {
    return NextResponse.json({ error: 'Filename is required' }, { status: 400 });
  }

  try {
    return NextResponse.json(await deleteContentByFilename(payload.filename));
  } catch (error) {
    return contentErrorResponse(error, 'Failed to delete file');
  }
}

function contentErrorResponse(error: unknown, fallback: string) {
  if (error instanceof ContentServiceError) {
    return NextResponse.json({ error: error.message }, { status: error.status });
  }

  return NextResponse.json(
    { error: error instanceof Error ? error.message : fallback },
    { status: 500 },
  );
}
