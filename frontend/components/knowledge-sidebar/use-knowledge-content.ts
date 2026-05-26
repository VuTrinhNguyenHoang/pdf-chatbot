'use client';

import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import type {
  ContentResponse,
  DeleteContentResponse,
  FileEntry,
} from '@/types/content';

const EMPTY_CONTENT: ContentResponse = { files: [], tables: [], images: [] };

export function useKnowledgeContent(
  refreshTrigger?: number,
  onDocumentDeleted?: (filename: string) => void,
) {
  const { toast } = useToast();
  const [data, setData] = useState<ContentResponse>(EMPTY_CONTENT);
  const [loading, setLoading] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState<string | null>(null);
  const [fileToDelete, setFileToDelete] = useState<FileEntry | null>(null);

  const fetchContent = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/content', { cache: 'no-store' });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchContent(); }, [fetchContent, refreshTrigger]);

  const deleteFile = async () => {
    if (!fileToDelete) return;

    setDeletingFilename(fileToDelete.filename);
    try {
      const res = await fetch('/api/content', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: fileToDelete.filename }),
      });
      const payload = await res.json() as DeleteContentResponse | { error: string };

      if (!res.ok) {
        throw new Error('error' in payload ? payload.error : 'Failed to delete file');
      }

      onDocumentDeleted?.(fileToDelete.filename);
      setFileToDelete(null);
      await fetchContent();
      toast({
        title: 'File deleted',
        description: `${fileToDelete.filename} was removed from the knowledge base`,
      });
    } catch (error) {
      toast({
        title: 'Delete failed',
        description: error instanceof Error ? error.message : 'Failed to delete file',
        variant: 'destructive',
      });
    } finally {
      setDeletingFilename(null);
    }
  };

  return {
    data,
    loading,
    deletingFilename,
    fileToDelete,
    setFileToDelete,
    fetchContent,
    deleteFile,
  };
}
