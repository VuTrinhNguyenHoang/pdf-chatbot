// app/api/ingest/route.ts
import { indexConfig } from '@/constants/graphConfigs';
import { langGraphServerClient } from '@/lib/langgraph-server';
import { NextRequest, NextResponse } from 'next/server';

// Configuration constants
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_FILE_TYPES = ['application/pdf'];

export async function POST(request: NextRequest) {
  try {
    if (!process.env.LANGGRAPH_INGESTION_ASSISTANT_ID) {
      return NextResponse.json(
        {
          error:
            'LANGGRAPH_INGESTION_ASSISTANT_ID is not set in your environment variables',
        },
        { status: 500 },
      );
    }

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
    if (files.length > 5) {
      return NextResponse.json(
        { error: 'Too many files. Maximum 5 files allowed.' },
        { status: 400 },
      );
    }

    // Validate file types and sizes
    const invalidFiles = files.filter((file) => {
      return (
        !ALLOWED_FILE_TYPES.includes(file.type) || file.size > MAX_FILE_SIZE
      );
    });

    if (invalidFiles.length > 0) {
      return NextResponse.json(
        {
          error:
            'Only PDF files are allowed and file size must be less than 10MB',
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
      'ingestion_graph',
      {
        input: {
          sources,
        },
        config: {
          configurable: {
            ...indexConfig,
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
