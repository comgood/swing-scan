// A row of fields that stacks to one column below 640 px (spec 0003 AC-5, AC-14).
import type * as React from "react";

import { cn } from "@/lib/utils";

const COLUMNS = {
  1: "sm:grid-cols-1",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-4",
} as const;

interface FormRowProps extends React.ComponentProps<"div"> {
  columns?: keyof typeof COLUMNS;
}

export function FormRow({ columns = 2, className, ...props }: FormRowProps) {
  return (
    <div
      data-slot="form-row"
      className={cn("grid grid-cols-1 gap-3 *:min-w-0", COLUMNS[columns], className)}
      {...props}
    />
  );
}
