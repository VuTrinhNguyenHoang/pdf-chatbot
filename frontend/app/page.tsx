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
import { client } from '@/lib/langgraph-client';
import {
  AgentState,
  documentType,
  PDFDocument,
  RetrieveDocumentsNodeUpdates,
  StreamActivity,
} from '@/types/graphTypes';
import { Card, CardContent } from '@/components/ui/card';

type ChatMessageItem = {
  role: 'user' | 'assistant';
  content: string;
  sources?: PDFDocument[];
  activity?: StreamActivity;
};

const GRAPH_NODES = new Set([
  'checkQueryType',
  'retrieveDocuments',
  'generateResponse',
  'directAnswer',
]);

function createInitialActivity(): StreamActivity {
  return {
    route: null,
    completedNodes: ['START'],
    activeNode: 'checkQueryType',
    isComplete: false,
  };
}

function markActivityNodeComplete(
  activity: StreamActivity,
  nodeName: string,
  nodeData: unknown,
): StreamActivity {
  if (!GRAPH_NODES.has(nodeName)) {
    return activity;
  }

  const completedNodes = new Set(activity.completedNodes);
  completedNodes.add('START');
  completedNodes.add(nodeName);

  let route = activity.route;
  let activeNode = activity.activeNode;
  let isComplete = activity.isComplete;

  if (
    nodeName === 'checkQueryType' &&
    nodeData &&
    typeof nodeData === 'object' &&
    'route' in nodeData
  ) {
    const nextRoute = (nodeData as { route?: unknown }).route;
    route =
      nextRoute === 'retrieve' || nextRoute === 'direct' ? nextRoute : route;
    activeNode =
      route === 'retrieve'
        ? 'retrieveDocuments'
        : route === 'direct'
          ? 'directAnswer'
          : 'unknown';
  } else if (nodeName === 'retrieveDocuments') {
    route = 'retrieve';
    activeNode = 'generateResponse';
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
  };
}

function markActivityStreaming(activity: StreamActivity): StreamActivity {
  if (activity.isComplete) {
    return activity;
  }

  if (activity.route === 'retrieve') {
    return { ...activity, activeNode: 'generateResponse' };
  }

  if (activity.route === 'direct') {
    return { ...activity, activeNode: 'directAnswer' };
  }

  return activity;
}

function completeActivity(activity: StreamActivity): StreamActivity {
  if (activity.isComplete) {
    return activity;
  }

  const completedNodes = new Set(activity.completedNodes);
  completedNodes.add('START');

  if (activity.route === 'retrieve') {
    completedNodes.add('generateResponse');
  } else if (activity.route === 'direct') {
    completedNodes.add('directAnswer');
  }

  completedNodes.add('END');

  return {
    ...activity,
    completedNodes: Array.from(completedNodes),
    activeNode: null,
    isComplete: true,
  };
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
  const { toast } = useToast(); // Add this hook
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null); // Track the AbortController
  const messagesEndRef = useRef<HTMLDivElement>(null); // Add this ref
  const lastRetrievedDocsRef = useRef<PDFDocument[]>([]); // useRef to store the last retrieved documents

  const updateLatestAssistantMessage = (
    updater: (message: ChatMessageItem) => ChatMessageItem,
  ) => {
    setMessages((prev) => {
      const nextMessages = [...prev];
      let index = -1;

      for (let i = nextMessages.length - 1; i >= 0; i -= 1) {
        if (nextMessages[i].role === 'assistant') {
          index = i;
          break;
        }
      }

      if (index === -1) {
        return prev;
      }

      nextMessages[index] = updater(nextMessages[index]);
      return nextMessages;
    });
  };

  useEffect(() => {
    // Create a thread when the component mounts
    const initThread = async () => {
      // Skip if we already have a thread
      if (threadId) return;

      try {
        const thread = await client.createThread();

        setThreadId(thread.thread_id);
      } catch (error) {
        console.error('Error creating thread:', error);
        toast({
          title: 'Error',
          description:
            'Error creating thread. Please make sure you have set the LANGGRAPH_API_URL environment variable correctly. ' +
            error,
          variant: 'destructive',
        });
      }
    };
    initThread();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !threadId || isLoading) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const userMessage = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage, sources: undefined }, // Clear sources for new user message
      {
        role: 'assistant',
        content: '',
        sources: undefined,
        activity: createInitialActivity(),
      }, // Clear sources for new assistant message
    ]);
    setInput('');
    setIsLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    lastRetrievedDocsRef.current = []; // Clear the last retrieved documents

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          threadId,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkStr = decoder.decode(value);
        const lines = chunkStr.split('\n').filter(Boolean);

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const sseString = line.slice('data: '.length);
          let sseEvent: any;
          try {
            sseEvent = JSON.parse(sseString);
          } catch (err) {
            console.error('Error parsing SSE line:', err, line);
            continue;
          }

          const { event, data } = sseEvent;

          if (event === 'messages/partial') {
            updateLatestAssistantMessage((message) => ({
              ...message,
              activity: markActivityStreaming(
                message.activity ?? createInitialActivity(),
              ),
            }));

            if (Array.isArray(data)) {
              const lastObj = data[data.length - 1];
              if (lastObj?.type === 'ai') {
                const partialContent = lastObj.content ?? '';

                if (typeof partialContent === 'string' && !partialContent.startsWith('{')) {
                  setMessages((prev) => {
                    const newArr = [...prev];
                    if (
                      newArr.length > 0 &&
                      newArr[newArr.length - 1].role === 'assistant'
                    ) {
                      newArr[newArr.length - 1].content = partialContent;
                      newArr[newArr.length - 1].sources =
                        lastRetrievedDocsRef.current;
                    }

                    return newArr;
                  });
                }
              }
            }
          } else if (event === 'updates' && data) {
            if (data && typeof data === 'object') {
              for (const [nodeName, nodeData] of Object.entries(data)) {
                updateLatestAssistantMessage((message) => ({
                  ...message,
                  activity: markActivityNodeComplete(
                    message.activity ?? createInitialActivity(),
                    nodeName,
                    nodeData,
                  ),
                }));
              }
            }

            if (
              data &&
              typeof data === 'object' &&
              'retrieveDocuments' in data &&
              data.retrieveDocuments &&
              Array.isArray(data.retrieveDocuments.documents)
            ) {
              const retrievedDocs = (data as RetrieveDocumentsNodeUpdates)
                .retrieveDocuments.documents as PDFDocument[];

              // // Handle documents here
              lastRetrievedDocsRef.current = retrievedDocs;
              console.log('Retrieved documents:', retrievedDocs);
            } else {
              // Clear the last retrieved documents if it's a direct answer
              lastRetrievedDocsRef.current = [];
            }
          } else {
            console.log('Unknown SSE event:', event, data);
          }
        }
      }

      updateLatestAssistantMessage((message) => ({
        ...message,
        activity: completeActivity(message.activity ?? createInitialActivity()),
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
        newArr[newArr.length - 1].content =
          'Sorry, there was an error processing your message.';
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

    const nonPdfFiles = selectedFiles.filter(
      (file) => file.type !== 'application/pdf',
    );
    if (nonPdfFiles.length > 0) {
      toast({
        title: 'Invalid file type',
        description: 'Please upload PDF files only',
        variant: 'destructive',
      });
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to upload files');
      }

      setFiles((prev) => [...prev, ...selectedFiles]);
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
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveFile = (fileToRemove: File) => {
    setFiles(files.filter((file) => file !== fileToRemove));
    toast({
      title: 'File removed',
      description: `${fileToRemove.name} has been removed`,
      variant: 'default',
    });
  };

  return (
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

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-background">
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
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                ) : (
                  <Paperclip className="h-4 w-4" />
                )}
              </Button>
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  isUploading ? 'Uploading PDF...' : 'Send a message...'
                }
                className="border-0 focus-visible:ring-0 focus-visible:ring-offset-0 h-12 bg-transparent"
                disabled={isUploading || isLoading || !threadId}
              />
              <Button
                type="submit"
                size="icon"
                className="rounded-none h-12"
                disabled={
                  !input.trim() || isUploading || isLoading || !threadId
                }
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
    </main>
  );
}
