// Rule builder (scope feature 10, spec 0008). Mounted on `/` by the scan workspace
// (`features/scan/scan-workspace.tsx`), which owns the reducer, the link and the scan.
export { builderErrors } from "./errors";
export { MAX_CONDITIONS, normaliseRule, OPERATORS } from "./is-rule";
export { JsonPanel, NOT_A_RULE } from "./json-panel";
export {
  builderReducer,
  defaultN,
  initBuilder,
  newCondition,
  type BuilderAction,
  type BuilderState,
  type RuleSource,
} from "./reducer";
export { MAX_ROWS_REASON, RuleBuilder, STALE_TEXT } from "./rule-builder";
export { decodeRule, encodeRule } from "./url-codec";

/** Decision 4's notice for a `?r=` that does not decode (shown by the workspace). */
export const BAD_LINK_NOTICE = "This link's rule could not be read. Showing the Breakout template.";
