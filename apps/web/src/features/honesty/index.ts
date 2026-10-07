// Research honesty guards (scope feature 13, spec 0004): parts features 9 and 12 place.
export { ProcedureNote, PROCEDURE_NOTE } from "./procedure-note";
export { OVERFIT_WARNING, RunTrialCounter, TrialCounter, trialCounterText } from "./trial-counter";
export {
  isOverTrialLimit,
  recordTrial,
  TRIAL_WARNING_AT,
  type Trial,
  type TrialCount,
  type TrialStores,
} from "./trial-store";
export { useTrialCount, type TrialCountState } from "./use-trial-count";
