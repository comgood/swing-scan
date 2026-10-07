// What went wrong with a request, in plain words, with a retry (spec 0003 AC-10).
// 422s never come here; they go to their fields (AC-7).
import { Banner } from "@/components/banner";
import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api-error";

interface ErrorStateProps {
  error: ApiError;
  onRetry?: () => void;
  headingLevel?: 2 | 3 | 4 | 5 | 6;
}

function describe(error: ApiError): { title: string; body: string; retry: boolean } {
  switch (error.kind) {
    case "network":
      return {
        title: "Can't reach the engine",
        body: "Check your connection and try again.",
        retry: true,
      };
    case "timeout":
      return {
        title: "The engine took too long",
        body: "It may be starting up. Try again.",
        retry: true,
      };
    case "http":
      if (error.status === 501) {
        return { title: "Not built yet", body: error.detail ?? "", retry: false };
      }
      if (error.status === 504) {
        return {
          title: "The engine took too long",
          body: "It may be starting up. Try again.",
          retry: true,
        };
      }
      return {
        title: "Something went wrong",
        body: `The API answered with status ${error.status}.`,
        retry: true,
      };
  }
}

export function ErrorState({ error, onRetry, headingLevel = 2 }: ErrorStateProps) {
  const { title, body, retry } = describe(error);
  const Heading = `h${headingLevel}` as const;
  return (
    <Banner variant="danger" title={<Heading className="text-sm font-medium">{title}</Heading>}>
      <div className="flex flex-col items-start gap-2">
        {body && <p>{body}</p>}
        {retry && onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </Banner>
  );
}
