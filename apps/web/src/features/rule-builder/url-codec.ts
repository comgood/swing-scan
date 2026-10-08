// The `?r=` link codec (spec 0008 decision 3): base64url, no padding, of the rule's compact
// UTF-8 JSON. Decoding is untrusted input: size capped, parsed in a try, then shape checked.
import type { Rule } from "@swing-scan/api-client";

import { normaliseRule } from "./is-rule";

/** A longer `?r=` is treated as a bad link before decoding. */
export const MAX_ENCODED_LENGTH = 8 * 1024;

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): Uint8Array {
  const base64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export function encodeRule(rule: Rule): string {
  return toBase64Url(new TextEncoder().encode(JSON.stringify(rule)));
}

/** The rule a `?r=` value carries, or null when it does not decode to the `Rule` shape. */
export function decodeRule(text: string, names: readonly string[]): Rule | null {
  if (text.length === 0 || text.length > MAX_ENCODED_LENGTH) return null;
  if (!/^[A-Za-z0-9_-]+$/.test(text)) return null;
  try {
    const json = new TextDecoder("utf-8", { fatal: true }).decode(fromBase64Url(text));
    return normaliseRule(JSON.parse(json), names);
  } catch {
    return null;
  }
}
