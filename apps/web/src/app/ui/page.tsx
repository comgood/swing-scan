// The hidden component gallery (spec 0003 AC-15): every part in every state, for keyboard,
// 375 px, and axe checks. Not linked from the header and not indexed.
import type { Metadata } from "next";

import { Gallery } from "./gallery";

export const metadata: Metadata = {
  title: "UI gallery · Swing Scan",
  robots: { index: false },
};

export default function UiGalleryPage() {
  return <Gallery />;
}
