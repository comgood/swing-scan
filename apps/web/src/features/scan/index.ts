// Template scan workspace (scope feature 8, spec 0005).
export { conditionText, operandColumns, operandLabel } from "./operands";
// The template list and the indicator catalog are shared with the report page: one query key,
// one cache, one implementation.
export { useIndicators, useTemplates } from "./queries";
export { DEFAULT_TEMPLATE_ID, pickTemplate, ScanWorkspace } from "./scan-workspace";
