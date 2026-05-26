import type { ElementType } from 'react';
import { cn } from '@/lib/utils';

export type KnowledgeTab = 'files' | 'tables' | 'images';

export interface KnowledgeTabItem {
  id: KnowledgeTab;
  label: string;
  icon: ElementType;
}

interface SidebarTabsProps {
  tabs: KnowledgeTabItem[];
  activeTab: KnowledgeTab;
  counts: Record<KnowledgeTab, number>;
  onChange: (tab: KnowledgeTab) => void;
}

export function SidebarTabs({
  tabs,
  activeTab,
  counts,
  onChange,
}: SidebarTabsProps) {
  return (
    <nav className="px-2 py-1.5 space-y-0.5 border-b shrink-0">
      {tabs.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={cn(
            'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-left transition-colors',
            activeTab === id
              ? 'bg-black text-white'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" />
          <span>{label}</span>
          <span className="ml-auto text-[10px] opacity-60">{counts[id]}</span>
        </button>
      ))}
    </nav>
  );
}
