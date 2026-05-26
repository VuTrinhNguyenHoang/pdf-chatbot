import { cn } from '@/lib/utils';

export function MarkdownTable({ content }: { content: string }) {
  const lines = content.split('\n').filter((line) => line.trim().startsWith('|'));
  if (lines.length < 2) {
    return (
      <pre className="text-xs font-mono bg-muted/40 rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
        {content}
      </pre>
    );
  }

  const parseRow = (line: string) =>
    line.split('|').slice(1, -1).map((cell) => cell.trim());
  const isSeparator = (line: string) => /^[\s|:-]+$/.test(line);

  const dataLines = lines.filter((line) => !isSeparator(line));
  const [headerLine, ...bodyLines] = dataLines;
  const headers = parseRow(headerLine);
  const rows = bodyLines.map(parseRow);

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-muted/60">
            {headers.map((header, index) => (
              <th
                key={index}
                className="px-3 py-2 text-left font-semibold border-b whitespace-nowrap"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={cn(
                rowIndex % 2 === 0 ? 'bg-white' : 'bg-muted/20',
                'hover:bg-muted/40',
              )}
            >
              {headers.map((_, cellIndex) => (
                <td
                  key={cellIndex}
                  className="px-3 py-1.5 border-b border-border/50 align-top"
                >
                  {row[cellIndex] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
