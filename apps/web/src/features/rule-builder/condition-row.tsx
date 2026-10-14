"use client";

// One condition row: a bubble reading the condition, which opens into the editor (left operand,
// operator, and a Number or Indicator right side; spec 0008 AC-6, decisions 7 and 9). Each part
// of the editor carries the colour its part of the bubble has, so it is clear which parameters
// belong to which side. The parts stack below 640 px (U-6).
import type { IndicatorSpec } from "@swing-scan/api-client";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { conditionText, operandLabel, OPERATOR_TEXT } from "@/features/scan/operands";

import type { RowErrors } from "./errors";
import { OPERATORS } from "./is-rule";
import { NumberOperandFields, OperandFields } from "./operand-fields";
import {
  defaultN,
  indOperand,
  switchRightKind,
  type BuilderAction,
  type Condition,
  type Operator,
} from "./reducer";

export const OPERATOR_LABELS: Record<Operator, string> = {
  ">": "> greater than",
  "<": "< less than",
  ">=": ">= at least",
  "<=": "<= at most",
  crosses_above: "crosses above",
  crosses_below: "crosses below",
};

export const LAST_ROW_REASON = "A rule needs at least 1 condition.";
export const DONE_LABEL = "Done";

/** One colour per part of the condition, on the bubble and on that part's parameters. */
const TINT = {
  left: "bg-info text-info-foreground",
  op: "bg-muted text-foreground",
  right: "bg-warning text-warning-foreground",
} as const;
const BOX = {
  left: "rounded-lg border border-info-foreground/30 bg-info/50 p-3",
  op: "rounded-lg border border-border bg-muted/50 p-3",
  right: "rounded-lg border border-warning-foreground/30 bg-warning/50 p-3",
} as const;

interface ConditionRowProps {
  index: number;
  condition: Condition;
  catalog: readonly IndicatorSpec[];
  dispatch: (action: BuilderAction) => void;
  canRemove: boolean;
  errors: RowErrors;
  /** The editor is open; closed, the row is just its bubble. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
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
  open,
  onOpenChange,
}: ConditionRowProps) {
  const { right } = condition;
  const reasonId = useId();
  const rightText = right.kind === "value" ? String(right.value) : operandLabel(right);
  return (
    <fieldset className="min-w-0 rounded-lg border p-4">
      <legend className="px-1 text-sm font-medium">Condition {index + 1}</legend>
      <details open={open} onToggle={(e) => onOpenChange(e.currentTarget.open)}>
        {/* The condition as one line, as the scan's columns name it (R-10: nothing hidden). */}
        <summary className="flex cursor-pointer flex-wrap items-center gap-2 rounded-md px-1 py-1 hover:bg-accent">
          {/* Read as one line, shown in three coloured parts that the editor below repeats. */}
          <span className="sr-only">{conditionText(condition)}</span>
          <span aria-hidden className="font-mono text-base font-semibold break-words">
            <span className={`rounded-sm px-1.5 py-0.5 ${TINT.left}`}>
              {operandLabel(condition.left)}
            </span>{" "}
            <span className={`rounded-sm px-1.5 py-0.5 ${TINT.op}`}>
              {OPERATOR_TEXT[condition.op]}
            </span>{" "}
            <span className={`rounded-sm px-1.5 py-0.5 ${TINT.right}`}>{rightText}</span>
          </span>
          <span className="text-xs text-muted-foreground">{open ? "Close" : "Edit"}</span>
        </summary>

        <div className="flex min-w-0 flex-col gap-4 pt-4">
          <GroupError message={errors.row} />

          <fieldset className={`flex min-w-0 flex-col gap-2 ${BOX.left}`}>
            <legend className="px-1 text-xs font-medium">Left side</legend>
            <GroupError message={errors.left.group} />
            <OperandFields
              operand={condition.left}
              catalog={catalog}
              errors={errors.left}
              onChange={(operand) => dispatch({ type: "setLeft", index, operand })}
            />
          </fieldset>

          <div className={`min-w-0 ${BOX.op}`}>
            <Field invalid={Boolean(errors.op)} className="sm:max-w-xs">
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
          </div>

          <fieldset className={`flex min-w-0 flex-col gap-2 ${BOX.right}`}>
            <legend className="px-1 text-xs font-medium">Right side</legend>
            <GroupError message={errors.right.group} />
            {right.kind === "value" ? (
              <NumberOperandFields
                value={right.value}
                catalog={catalog}
                errors={errors.right}
                onChange={(value) =>
                  dispatch({ type: "setRight", index, operand: { kind: "value", value } })
                }
                onPickIndicator={(ind) =>
                  // The picked indicator's own default window, as the left side does: the list
                  // names the indicator now, so there is no generic "Indicator" to start at.
                  dispatch({
                    type: "setRight",
                    index,
                    operand: indOperand(ind, defaultN(ind, catalog)),
                  })
                }
              />
            ) : (
              <OperandFields
                operand={right}
                catalog={catalog}
                errors={errors.right}
                onChange={(operand) => dispatch({ type: "setRight", index, operand })}
                onPickNumber={() =>
                  dispatch({ type: "setRight", index, operand: switchRightKind("value") })
                }
              />
            )}
          </fieldset>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => onOpenChange(false)}>
              {DONE_LABEL}
            </Button>
            <Button
              variant="destructive"
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
        </div>
      </details>
    </fieldset>
  );
}
