'use client';

import type React from 'react';

import { useToast } from '@/hooks/use-toast';
import { useRef, useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Paperclip, ArrowUp, Loader2 } from 'lucide-react';
import { ExamplePrompts } from '@/components/example-prompts';
import { ChatMessage } from '@/components/chat-message';
import { FilePreview } from '@/components/file-preview';
import { KnowledgeSidebar } from '@/components/knowledge-sidebar';
import { client } from '@/lib/langgraph-client';
import { PDFDocument, StreamActivity } from '@/types/graphTypes';

type ChatMessageItem = {
  role: 'user' | 'assistant';
  content: string;
  sources?: PDFDocument[];
  activity?: StreamActivity;
};

const GRAPH_NODES = new Set([
  'checkQueryType',
  'retrieveDocuments',
  'checkEnough',
  'generateResponse',
  'directAnswer',
]);

function createInitialActivity(): StreamActivity {
  return {
    route: null,
    completedNodes: ['START'],
    activeNode: 'checkQueryType',
    isComplete: false,
    iterationCount: 0,
  };
}

function markActivityNodeComplete(
  activity: StreamActivity,
  nodeName: string,
  nodeData: unknown,
): StreamActivity {
  if (!GRAPH_NODES.has(nodeName)) return activity;

  const completedNodes = new Set(activity.completedNodes);
  completedNodes.add('START');
  completedNodes.add(nodeName);

  let { route, activeNode, isComplete, iterationCount } = activity;

  if (
    nodeName === 'checkQueryType' &&
    nodeData &&
    typeof nodeData === 'object' &&
    'route' in nodeData
  ) {
    const next = (nodeData as { route?: unknown }).route;
    route = next === 'retrieve' || next === 'direct' ? next : route;
    activeNode =
      route === 'retrieve'
        ? 'retrieveDocuments'
        : route === 'direct'
          ? 'directAnswer'
          : 'unknown';
  } else if (nodeName === 'retrieveDocuments') {
    route = 'retrieve';
    activeNode = 'checkEnough';
  } else if (nodeName === 'checkEnough') {
    const data = nodeData as { iteration_count?: number; is_sufficient?: boolean } | null;
    iterationCount = data?.iteration_count ?? iterationCount;
    activeNode = data?.is_sufficient === false ? 'retrieveDocuments' : 'generateResponse';
  } else if (nodeName === 'generateResponse' || nodeName === 'directAnswer') {
    completedNodes.add('END');
    activeNode = null;
    isComplete = true;
  }

  return {
    ...activity,
    route,
    completedNodes: Array.from(completedNodes),
    activeNode,
    isComplete,
    iterationCount,
  };
}

function markActivityStreaming(activity: StreamActivity): StreamActivity {
  if (activity.isComplete) return activity;
  if (activity.route === 'retrieve') return { ...activity, activeNode: 'generateResponse' };
  if (activity.route === 'direct') return { ...activity, activeNode: 'directAnswer' };
  return activity;
}

function completeActivity(activity: StreamActivity): StreamActivity {
  if (activity.isComplete) return activity;
  const completedNodes = new Set(activity.completedNodes);
  completedNodes.add('START');
  if (activity.route === 'retrieve') completedNodes.add('generateResponse');
  else if (activity.route === 'direct') completedNodes.add('directAnswer');
  completedNodes.add('END');
  return { ...activity, completedNodes: Array.from(completedNodes), activeNode: null, isComplete: true };
}

function failActivity(activity: StreamActivity, error: unknown): StreamActivity {
  return {
    ...activity,
    activeNode: activity.activeNode ?? 'unknown',
    isComplete: true,
    error: error instanceof Error ? error.message : 'Unknown streaming error',
  };
}

export default function Home() {
  const { toast } = useToast();
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastRetrievedDocsRef = useRef<PDFDocument[]>([]);

  const updateLatestAssistantMessage = (
    updater: (message: ChatMessageItem) => ChatMessageItem,
  ) => {
    setMessages((prev) => {
      const next = [...prev];
      let idx = -1;
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === 'assistant') { idx = i; break; }
      }
      if (idx === -1) return prev;
      next[idx] = updater(next[idx]);
      return next;
    });
  };

  useEffect(() => {
    if (threadId) return;
    client.createThread()
      .then((t) => setThreadId(t.thread_id))
      .catch((error) => {
        console.error('Error creating thread:', error);
        toast({
          title: 'Error',
          description:
            'Error creating thread. Please make sure you have set the LANGGRAPH_API_URL environment variable correctly. ' + error,
          variant: 'destructive',
        });
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !threadId || isLoading) return;

    abortControllerRef.current?.abort();

    const userMessage = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage, sources: undefined },
      { role: 'assistant', content: '', sources: undefined, activity: createInitialActivity() },
    ]);
    setInput('');
    setIsLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    lastRetrievedDocsRef.current = [];

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, threadId }),
        signal: abortController.signal,
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split('\n').filter(Boolean);
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let sseEvent: { event: string; data: unknown };
          try { sseEvent = JSON.parse(line.slice('data: '.length)); }
          catch { continue; }

          const { event, data } = sseEvent;

          if (event === 'messages/partial') {
            updateLatestAssistantMessage((msg) => ({
              ...msg,
              activity: markActivityStreaming(msg.activity ?? createInitialActivity()),
            }));

            if (Array.isArray(data)) {
              const lastObj = data[data.length - 1];
              if (lastObj?.type === 'ai') {
                const partialContent = lastObj.content ?? '';
                if (typeof partialContent === 'string' && !partialContent.startsWith('{')) {
                  setMessages((prev) => {
                    const newArr = [...prev];
                    if (newArr.length > 0 && newArr[newArr.length - 1].role === 'assistant') {
                      newArr[newArr.length - 1].content = partialContent;
                      newArr[newArr.length - 1].sources = lastRetrievedDocsRef.current;
                    }
                    return newArr;
                  });
                }
              }
            }
          } else if (event === 'updates' && data) {
            if (data && typeof data === 'object') {
              for (const [nodeName, nodeData] of Object.entries(data)) {
                updateLatestAssistantMessage((msg) => ({
                  ...msg,
                  activity: markActivityNodeComplete(
                    msg.activity ?? createInitialActivity(),
                    nodeName,
                    nodeData,
                  ),
                }));
              }
            }

            const updates = data as Record<string, unknown>;
            if ('retrieveDocuments' in updates) {
              const docs = (updates.retrieveDocuments as { documents?: PDFDocument[] })?.documents;
              if (Array.isArray(docs)) {
                const seen = new Set(lastRetrievedDocsRef.current.map((d) => d.metadata?.uuid));
                const newDocs = docs.filter((d) => !seen.has(d.metadata?.uuid));
                lastRetrievedDocsRef.current = [...lastRetrievedDocsRef.current, ...newDocs];
              }
            } else if ('directAnswer' in updates) {
              lastRetrievedDocsRef.current = [];
            }
            // checkEnough / generateResponse / checkQueryType must not touch the docs ref
          } else {
            console.log('Unknown SSE event:', event, data);
          }
        }
      }

      updateLatestAssistantMessage((msg) => ({
        ...msg,
        activity: completeActivity(msg.activity ?? createInitialActivity()),
      }));
    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: 'Error',
        description:
          'Failed to send message. Please try again.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
      setMessages((prev) => {
        const newArr = [...prev];
        newArr[newArr.length - 1].content = 'Sorry, there was an error processing your message.';
        newArr[newArr.length - 1].activity = failActivity(
          newArr[newArr.length - 1].activity ?? createInitialActivity(),
          error,
        );
        return newArr;
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    const nonPdfFiles = selectedFiles.filter((file) => file.type !== 'application/pdf');
    if (nonPdfFiles.length > 0) {
      toast({ title: 'Invalid file type', description: 'Please upload PDF files only', variant: 'destructive' });
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append('files', file));

      const response = await fetch('/api/ingest', { method: 'POST', body: formData });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to upload files');
      }

      setFiles((prev) => [...prev, ...selectedFiles]);
      setSidebarRefresh((n) => n + 1);
      toast({
        title: 'Success',
        description: `${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''} uploaded successfully`,
        variant: 'default',
      });
    } catch (error) {
      console.error('Error uploading files:', error);
      toast({
        title: 'Upload failed',
        description:
          'Failed to upload files. Please try again.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (fileToRemove: File) => {
    setFiles(files.filter((file) => file !== fileToRemove));
    toast({ title: 'File removed', description: `${fileToRemove.name} has been removed`, variant: 'default' });
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left sidebar ─ 2/10 */}
      <aside className="w-56 min-w-[200px] shrink-0">
        <KnowledgeSidebar refreshTrigger={sidebarRefresh} />
      </aside>

      {/* Right panel ─ 8/10: original layout preserved exactly */}
      <div className="flex-1 overflow-y-auto min-w-0">
        <main className="flex min-h-screen flex-col items-center p-4 md:p-24 max-w-5xl mx-auto w-full">
          {messages.length === 0 ? (
            <>
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <p className="font-medium text-muted-foreground max-w-md mx-auto">
                    Upload PDF files, ingest them into the knowledge base, and ask
                    questions about their content.
                  </p>
                </div>
              </div>
              <ExamplePrompts onPromptSelect={setInput} />
            </>
          ) : (
            <div className="w-full space-y-4 mb-20">
              {messages.map((message, i) => (
                <ChatMessage key={i} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>
      </div>

      {/* Input bar ─ fixed to viewport bottom, starts after sidebar */}
      <div className="fixed bottom-0 left-56 right-0 p-4 bg-background">
        <div className="max-w-5xl mx-auto space-y-4">
          {files.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {files.map((file, index) => (
                <FilePreview
                  key={`${file.name}-${index}`}
                  file={file}
                  onRemove={() => handleRemoveFile(file)}
                />
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="relative">
            <div className="flex gap-2 border rounded-md overflow-hidden bg-gray-50">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".pdf"
                multiple
                className="hidden"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="rounded-none h-12"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Paperclip className="h-4 w-4" />
                )}
              </Button>
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isUploading ? 'Uploading PDF...' : 'Send a message...'}
                className="border-0 focus-visible:ring-0 focus-visible:ring-offset-0 h-12 bg-transparent"
                disabled={isUploading || isLoading || !threadId}
              />
              <Button
                type="submit"
                size="icon"
                className="rounded-none h-12"
                disabled={!input.trim() || isUploading || isLoading || !threadId}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
