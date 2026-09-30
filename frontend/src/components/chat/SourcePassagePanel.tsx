import { ExternalLinkIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { CitationSource } from "@/lib/chat-messages"

type SourcePassagePanelProps = {
  citation: CitationSource | null
  onClose: () => void
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
})

function sourceLocation(citation: CitationSource) {
  const values = []
  if (citation.page !== null) {
    values.push(`Page ${citation.page}`)
  }
  if (citation.section) {
    values.push(citation.section)
  }
  return values.join(" · ") || "Location unavailable"
}

export function SourcePassagePanel({
  citation,
  onClose,
}: SourcePassagePanelProps) {
  return (
    <Sheet open={citation !== null} onOpenChange={(open) => !open && onClose()}>
      {citation ? (
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>
              [{citation.position}] {citation.company_name ?? citation.ticker}
            </SheetTitle>
            <SheetDescription>
              {citation.ticker} · {citation.form} ·{" "}
              {dateFormatter.format(new Date(`${citation.filing_date}T00:00:00`))}
            </SheetDescription>
          </SheetHeader>

          <div className="flex flex-1 flex-col gap-6 px-6 pb-6">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Filing location
              </p>
              <p className="mt-1 text-sm">{sourceLocation(citation)}</p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Exact cited passage
              </p>
              <blockquote className="mt-2 border-l-2 pl-4 text-sm leading-6 text-foreground">
                {citation.quoted_text}
              </blockquote>
            </div>

            <div className="mt-auto border-t pt-4">
              <p className="mb-3 text-xs text-muted-foreground">
                SEC accession {citation.accession_number}
              </p>
              <Button asChild variant="outline">
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open filing
                  <ExternalLinkIcon data-icon="inline-end" />
                </a>
              </Button>
            </div>
          </div>
        </SheetContent>
      ) : null}
    </Sheet>
  )
}
