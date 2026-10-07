// Errors that belong to the whole request, not one field (spec 0003 AC-7, U-7).
import { Banner } from "@/components/banner";

interface FormErrorSummaryProps {
  errors: string[];
  title?: string;
}

export function FormErrorSummary({
  errors,
  title = "Fix this before running",
}: FormErrorSummaryProps) {
  if (errors.length === 0) return null;
  return (
    <Banner variant="danger" title={title}>
      {errors.length === 1 ? (
        <p>{errors[0]}</p>
      ) : (
        <ul className="ml-4 list-disc">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </Banner>
  );
}
