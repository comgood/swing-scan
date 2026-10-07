// A page level message with an icon and words (spec 0003 AC-11). Never closable.
// info and warning are static page content (no live role); danger is role="alert" and is only
// inserted when an error happens.
import { CircleAlert, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type * as React from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

type BannerVariant = "info" | "warning" | "danger";

const ICONS: Record<BannerVariant, LucideIcon> = {
  info: Info,
  warning: TriangleAlert,
  danger: CircleAlert,
};

interface BannerProps {
  variant: BannerVariant;
  title?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function Banner({ variant, title, children, className }: BannerProps) {
  const Icon = ICONS[variant];
  return (
    <Alert
      variant={variant}
      role={variant === "danger" ? "alert" : undefined}
      data-variant={variant}
      className={className}
    >
      <Icon aria-hidden="true" />
      {title !== undefined && <AlertTitle>{title}</AlertTitle>}
      {children !== undefined && <AlertDescription>{children}</AlertDescription>}
    </Alert>
  );
}
