// "Nothing here yet" with a title and one line hint, on the preset's Empty (spec 0003 AC-11).
import type * as React from "react";

import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

interface EmptyStateProps {
  title: string;
  hint?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, hint, className }: EmptyStateProps) {
  return (
    <Empty className={className}>
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        {hint !== undefined && <EmptyDescription>{hint}</EmptyDescription>}
      </EmptyHeader>
    </Empty>
  );
}
