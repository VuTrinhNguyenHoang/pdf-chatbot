// app/api/ingest/route.ts
import { getIndexConfig, getIngestionAssistantId } from '@/config/server';
import { getPublicConfig } from '@/config/public';
import { langGraphServerClient } from '@/lib/langgraph-server';
import { NextRequest, NextResponse } from 'next/server';

const ALLOWED_FILE_TYPES = ['application/pdf'];

export async function POST(request: NextRequest) {
  try {
    const assistantId = getIngestionAssistantId();
    const publicConfig = getPublicConfig();
    const formData = await request.formData();
    const files: File[] = [];

    for (const [key, value] of formData.entries()) {
      if (key === 'files' && value instanceof File) {
        files.push(value);
      }
    }

    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'No files provided' }, { status: 400 });
    }

    // Validate file count
    if (files.length > publicConfig.maxUploadFiles) {
      return NextResponse.json(
        {
          error: `Too many files. Maximum ${publicConfig.maxUploadFiles} files allowed.`,
        },
        { status: 400 },
      );
    }

    // Validate file types and sizes
    const invalidFiles = files.filter((file) => {
      return (
        !ALLOWED_FILE_TYPES.includes(file.type)
        || file.size > publicConfig.maxUploadBytes
      );
    });

    if (invalidFiles.length > 0) {
      return NextResponse.json(
        {
          error: `Only PDF files are allowed and file size must be less than ${publicConfig.maxUploadMb}MB`,
        },
        { status: 400 },
      );
    }

    const sources = await Promise.all(
      files.map(async (file) => ({
        filename: file.name,
        mimeType: file.type,
        contentBase64: Buffer.from(await file.arrayBuffer()).toString('base64'),
      })),
    );

    // Run the ingestion graph
    const thread = await langGraphServerClient.createThread();
    await langGraphServerClient.client.runs.wait(
      thread.thread_id,
      assistantId,
      {
        input: {
          sources,
        },
        config: {
          configurable: {
            ...getIndexConfig(),
          },
        },
      },
    );

    return NextResponse.json({
      message: 'Documents ingested successfully',
      threadId: thread.thread_id,
    });
  } catch (error: any) {
    console.error('Error processing files:', error);
    return NextResponse.json(
      { error: 'Failed to process files', details: error.message },
      { status: 500 },
    );
  }
}
