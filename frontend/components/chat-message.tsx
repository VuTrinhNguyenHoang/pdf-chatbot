import { Activity, ChevronRight, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useState } from 'react';
import { PDFDocument, StreamActivity } from '@/types/graphTypes';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { cn } from '@/lib/utils';

interface ChatMessageProps {
  message: {
    role: 'user' | 'assistant';
    content: string;
    sources?: PDFDocument[];
    activity?: StreamActivity;
  };
}

const ACTIVITY_PATHS = {
  retrieve: [
    'START',
    'checkQueryType',
    'retrieveDocuments',
    'checkEnough',
    'generateResponse',
    'END',
  ],
  direct: ['START', 'checkQueryType', 'directAnswer', 'END'],
  unknown: ['START', 'checkQueryType', '...', 'END'],
};

const ACTIVITY_LABELS: Record<string, string> = {
  START: 'START',
  checkQueryType: 'checkQueryType',
  retrieveDocuments: 'retrieveDocuments',
  checkEnough: 'checkEnough',
  generateResponse: 'generateResponse',
  directAnswer: 'directAnswer',
  '...': '...',
  END: 'END',
};

function getSourceName(source: PDFDocument): string {
  const metadata = source.metadata as Record<string, any> | undefined;
  const rawSource = metadata?.source_file || metadata?.filename || metadata?.source;

  if (!rawSource) {
    return 'N/A';
  }

  return String(rawSource).split('/').pop() || String(rawSource);
}

function getPageLabel(source: PDFDocument): string {
  const metadata = source.metadata as Record<string, any> | undefined;
  const pageStart = metadata?.page_start ?? metadata?.loc?.pageNumber;
  const pageEnd = metadata?.page_end;

  if (pageStart == null) {
    return 'N/A';
  }

  if (pageEnd && pageEnd !== pageStart) {
    return `${pageStart}-${pageEnd}`;
  }

  return `${pageStart}`;
}

function getSourceTitle(source: PDFDocument): string | undefined {
  const metadata = source.metadata as Record<string, any> | undefined;

  return (
    metadata?.table_title ||
    metadata?.image_title ||
    metadata?.title ||
    metadata?.content_type
  );
}

function getActivityPath(activity: StreamActivity): string[] {
  if (activity.route === 'retrieve') {
    return ACTIVITY_PATHS.retrieve;
  }

  if (activity.route === 'direct') {
    return ACTIVITY_PATHS.direct;
  }

  return ACTIVITY_PATHS.unknown;
}

function getActivityStepStatus(
  activity: StreamActivity,
  stepId: string,
): 'pending' | 'active' | 'complete' | 'error' {
  const isActive =
    activity.activeNode === stepId ||
    (stepId === '...' && activity.activeNode === 'unknown');

  if (activity.error && isActive) {
    return 'error';
  }

  if (activity.completedNodes.includes(stepId)) {
    return 'complete';
  }

  if (isActive) {
    return 'active';
  }

  return 'pending';
}

function getActivitySummary(activity: StreamActivity): string {
  if (activity.error) return 'Error';
  if (activity.isComplete) return 'Complete';

  if (activity.activeNode) {
    const label = ACTIVITY_LABELS[activity.activeNode] ?? activity.activeNode;
    if (activity.iterationCount && activity.iterationCount > 1) {
      return `${label} (attempt ${activity.iterationCount}/3)`;
    }
    return label;
  }

  return 'Pending';
}

function ActivityTrail({ activity }: { activity: StreamActivity }) {
  const path = getActivityPath(activity);

  return (
    <Accordion type="single" collapsible className="w-full mt-2">
      <AccordionItem value="activity" className="border-b-0">
        <AccordionTrigger className="text-sm py-2 justify-start gap-2 hover:no-underline">
          <Activity className="h-4 w-4" />
          <span>View Activity</span>
          <span className="text-xs text-muted-foreground">
            ({getActivitySummary(activity)})
          </span>
        </AccordionTrigger>
        <AccordionContent>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {path.map((stepId, index) => {
              const status = getActivityStepStatus(activity, stepId);

              return (
                <div
                  key={`${stepId}-${index}`}
                  className="flex items-center gap-1.5"
                >
                  <span
                    className={cn(
                      'inline-flex h-7 items-center rounded-md border px-2 font-mono text-[11px] leading-none',
                      status === 'complete' &&
                        'border-foreground/20 bg-background text-foreground',
                      status === 'active' &&
                        'border-primary bg-primary text-primary-foreground shadow-sm',
                      status === 'pending' &&
                        'border-border bg-background/60 text-muted-foreground',
                      status === 'error' &&
                        'border-destructive/30 bg-destructive/10 text-destructive',
                    )}
                  >
                    {status === 'active' && (
                      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
                    )}
                    {ACTIVITY_LABELS[stepId] ?? stepId}
                  </span>
                  {index < path.length - 1 && (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </div>
              );
            })}
          </div>
          {activity.error && (
            <p className="mt-2 text-xs text-destructive">{activity.error}</p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const isLoading = message.role === 'assistant' && message.content === '';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const showSources =
    message.role === 'assistant' &&
    message.sources &&
    message.sources.length > 0;
  const showActivity = message.role === 'assistant' && !!message.activity;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] min-w-0 ${isUser ? 'bg-black text-white' : 'bg-muted'} rounded-2xl px-4 py-2`}
      >
        {isLoading ? (
          <div className="flex space-x-1 h-6 items-center">
            <div className="w-1.5 h-1.5 bg-current rounded-full animate-[loading_1s_ease-in-out_infinite]" />
            <div className="w-1.5 h-1.5 bg-current rounded-full animate-[loading_1s_ease-in-out_0.2s_infinite]" />
            <div className="w-1.5 h-1.5 bg-current rounded-full animate-[loading_1s_ease-in-out_0.4s_infinite]" />
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap">{message.content}</p>
            {!isUser && (
              <div className="flex gap-2 mt-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleCopy}
                  title={copied ? 'Copied!' : 'Copy to clipboard'}
                >
                  <Copy
                    className={`h-4 w-4 ${copied ? 'text-green-500' : ''}`}
                  />
                </Button>
              </div>
            )}
          </>
        )}
        {showActivity && message.activity && (
          <ActivityTrail activity={message.activity} />
        )}
        {showSources && message.sources && (
          <Accordion type="single" collapsible className="w-full mt-2">
            <AccordionItem value="sources" className="border-b-0">
              <AccordionTrigger className="text-sm py-2 justify-start gap-2 hover:no-underline">
                View Sources ({message.sources.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {message.sources?.map((source, index) => {
                    const sourceName = getSourceName(source);
                    const pageLabel = getPageLabel(source);
                    const sourceTitle = getSourceTitle(source);

                    return (
                      <Card
                        key={index}
                        className="bg-background/50 transition-all duration-200 hover:bg-background hover:shadow-md hover:scale-[1.02] cursor-pointer"
                      >
                        <CardContent className="p-3">
                          <p className="text-sm font-medium truncate">
                            {sourceName}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Page {pageLabel}
                          </p>
                          {sourceTitle && (
                            <p className="text-xs text-muted-foreground truncate">
                              {sourceTitle}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </div>
    </div>
  );
}
