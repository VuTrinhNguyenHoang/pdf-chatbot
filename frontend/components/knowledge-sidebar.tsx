'use client';

import { useState } from 'react';
import { FileText, Table2, Image, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { DeleteDocumentDialog } from './knowledge-sidebar/delete-document-dialog';
import { FilesList } from './knowledge-sidebar/files-list';
import { ImagesList } from './knowledge-sidebar/images-list';
import {
  SidebarTabs,
  type KnowledgeTab,
  type KnowledgeTabItem,
} from './knowledge-sidebar/sidebar-tabs';
import { TablesList } from './knowledge-sidebar/tables-list';
import { useKnowledgeContent } from './knowledge-sidebar/use-knowledge-content';

const TABS: KnowledgeTabItem[] = [
  { id: 'files', label: 'Files', icon: FileText },
  { id: 'tables', label: 'Tables', icon: Table2 },
  { id: 'images', label: 'Images', icon: Image },
];

interface KnowledgeSidebarProps {
  refreshTrigger?: number;
  onDocumentDeleted?: (filename: string) => void;
}

export function KnowledgeSidebar({
  refreshTrigger,
  onDocumentDeleted,
}: KnowledgeSidebarProps) {
  const [activeTab, setActiveTab] = useState<KnowledgeTab>('files');
  const {
    data,
    loading,
    deletingFilename,
    fileToDelete,
    setFileToDelete,
    fetchContent,
    deleteFile,
  } = useKnowledgeContent(refreshTrigger, onDocumentDeleted);

  const counts: Record<KnowledgeTab, number> = {
    files: data.files.length,
    tables: data.tables.length,
    images: data.images.length,
  };

  return (
    <div className="flex flex-col h-full border-r bg-muted/20 overflow-hidden">
      <div className="px-3 py-2.5 border-b flex items-center justify-between shrink-0">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Knowledge
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={fetchContent}
          disabled={loading}
          title="Refresh"
        >
          <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
        </Button>
      </div>

      <SidebarTabs
        tabs={TABS}
        activeTab={activeTab}
        counts={counts}
        onChange={setActiveTab}
      />

      <div className="flex-1 overflow-y-auto p-2">
        {activeTab === 'files' && (
          <FilesList
            files={data.files}
            deletingFilename={deletingFilename}
            onDeleteClick={setFileToDelete}
          />
        )}
        {activeTab === 'tables' && <TablesList tables={data.tables} />}
        {activeTab === 'images' && <ImagesList images={data.images} />}
      </div>

      <DeleteDocumentDialog
        file={fileToDelete}
        deletingFilename={deletingFilename}
        onClose={() => setFileToDelete(null)}
        onDelete={deleteFile}
      />
    </div>
  );
}
