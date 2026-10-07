"use client";

// One condition row: left operand, operator, and a Number or Indicator right side
// (spec 0008 AC-6, decisions 7 and 9). The parts stack below 640 px (U-6).
import type { IndicatorSpec } from "@swing-scan/api-client";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { RowErrors } from "./errors";
import { OPERATORS } from "./is-rule";
import { OperandFields, RequiredNumber } from "./operand-fields";
import { switchRightKind, type Condition, type Operator, type BuilderAction } from "./reducer";

export const OPERATOR_LABELS: Record<Operator, string> = {
  ">": "> greater than",
  "<": "< less than",
  ">=": ">= at least",
  "<=": "<= at most",
  crosses_above: "crosses above",
  crosses_below: "crosses below",
};

export const LAST_ROW_REASON = "A rule needs at least 1 condition.";

interface ConditionRowProps {
  index: number;
  condition: Condition;
  catalog: readonly IndicatorSpec[];
  dispatch: (action: BuilderAction) => void;
  canRemove: boolean;
  errors: RowErrors;
}

function GroupError({ message }: { message?: string }) {
  return message ? <p className="text-sm text-destructive">{message}</p> : null;
}

export function ConditionRow({
  index,
  condition,
  catalog,
  dispatch,
  canRemove,
  errors,
}: ConditionRowProps) {
  const { right } = condition;
  const reasonId = useId();
  return (
    <fieldset className="flex min-w-0 flex-col gap-4 rounded-lg border p-4">
      <legend className="px-1 text-sm font-medium">Condition {index + 1}</legend>
      <GroupError message={errors.row} />

      <fieldset className="flex min-w-0 flex-col gap-2">
        <legend className="text-xs font-medium text-muted-foreground">Left side</legend>
        <GroupError message={errors.left.group} />
        <OperandFields
          operand={condition.left}
          catalog={catalog}
          errors={errors.left}
          onChange={(operand) => dispatch({ type: "setLeft", index, operand })}
        />
      </fieldset>

      <div className="grid min-w-0 grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-2">
        <Field invalid={Boolean(errors.op)}>
          <FieldLabel>Operator</FieldLabel>
          <NativeSelect
            value={condition.op}
            onChange={(e) => dispatch({ type: "setOp", index, op: e.target.value as Operator })}
          >
            {OPERATORS.map((op) => (
              <NativeSelectOption key={op} value={op}>
                {OPERATOR_LABELS[op]}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldError>{errors.op}</FieldError>
        </Field>
        <Field>
          <FieldLabel>Compare with</FieldLabel>
          <NativeSelect
            value={right.kind}
            onChange={(e) => {
              const kind = e.target.value as Condition["right"]["kind"];
              if (kind !== right.kind) {
                dispatch({ type: "setRight", index, operand: switchRightKind(kind) });
              }
            }}
          >
            <NativeSelectOption value="value">Number</NativeSelectOption>
            <NativeSelectOption value="ind">Indicator</NativeSelectOption>
          </NativeSelect>
        </Field>
      </div>

      <fieldset className="flex min-w-0 flex-col gap-2">
        <legend className="text-xs font-medium text-muted-foreground">Right side</legend>
        <GroupError message={errors.right.group} />
        {right.kind === "value" ? (
          <RequiredNumber
            label="Number"
            value={right.value}
            error={errors.right.value}
            onChange={(value) =>
              dispatch({ type: "setRight", index, operand: { kind: "value", value } })
            }
          />
        ) : (
          <OperandFields
            operand={right}
            catalog={catalog}
            errors={errors.right}
            onChange={(operand) => dispatch({ type: "setRight", index, operand })}
          />
        )}
      </fieldset>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!canRemove}
          aria-describedby={canRemove ? undefined : reasonId}
          onClick={() => dispatch({ type: "remove", index })}
        >
          Remove condition {index + 1}
        </Button>
        {!canRemove && (
          <span id={reasonId} className="text-xs text-muted-foreground">
            {LAST_ROW_REASON}
          </span>
        )}
      </div>
    </fieldset>
  );
}
