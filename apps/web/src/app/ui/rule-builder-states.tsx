"use client";

// The rule builder's states for the /ui gallery (spec 0008 AC-10). Each one is live: edit it to
// see the reducer at work. Invented rules and catalog only.
import type { Rule } from "@swing-scan/api-client";
import { useReducer, type ReactNode } from "react";

import { Banner } from "@/components/banner";
import {
  BAD_LINK_NOTICE,
  builderReducer,
  initBuilder,
  JsonPanel,
  newCondition,
  RuleBuilder,
} from "@/features/rule-builder";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";

import { SAMPLE_BUILDER_422, SAMPLE_CATALOG, SAMPLE_RULE } from "./sample";

const ONE_ROW: Rule = { name: "My rule", conditions: [newCondition()] };
const EIGHT_ROWS: Rule = {
  name: "Eight conditions",
  conditions: Array.from({ length: 8 }, newCondition),
};
const SAMPLE_ERRORS = fieldErrorsFrom422(SAMPLE_BUILDER_422);
const NAMES = SAMPLE_CATALOG.map((s) => s.name);

function State({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div
      role="group"
      aria-labelledby={`builder-state-${id}`}
      className="flex min-w-0 flex-col gap-2 rounded-lg border p-4"
    >
      <h3 id={`builder-state-${id}`} className="text-sm font-medium">
        {label}
      </h3>
      {children}
    </div>
  );
}

function Builder({ rule, errors, stale }: { rule: Rule; errors?: FieldErrors; stale?: boolean }) {
  const [state, dispatch] = useReducer(builderReducer, rule, (r) => initBuilder(r, "custom"));
  return (
    <RuleBuilder
      state={state}
      dispatch={dispatch}
      catalog={SAMPLE_CATALOG}
      errors={errors}
      stale={stale}
      onRun={() => dispatch({ type: "ran" })}
    />
  );
}

export function RuleBuilderStates() {
  return (
    <>
      <State id="one" label="One default row (remove disabled)">
        <Builder rule={ONE_ROW} />
      </State>
      <State id="indicator" label="Number and indicator right sides">
        <Builder rule={SAMPLE_RULE} />
      </State>
      <State id="eight" label="Eight rows (add disabled)">
        <Builder rule={EIGHT_ROWS} />
      </State>
      <State id="error" label="422 on a right side n">
        <Builder rule={SAMPLE_RULE} errors={SAMPLE_ERRORS} />
      </State>
      <State id="stale" label="Stale results">
        <Builder rule={SAMPLE_RULE} stale />
      </State>
      <State id="bad-link" label="Bad link notice">
        <Banner variant="info">{BAD_LINK_NOTICE}</Banner>
      </State>
      <State id="json" label="JSON panel with Not a rule">
        <JsonPanel
          rule={SAMPLE_RULE}
          names={NAMES}
          onLoad={() => {}}
          defaultOpen
          defaultDraft='{"name": "half a rule"}'
          defaultError
        />
      </State>
    </>
  );
}
