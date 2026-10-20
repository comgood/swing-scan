// Leaving the page after a sign in, a sign out or a deletion (spec 0015).
//
// Not `useRouter()`: `apps/web/AGENTS.md` keeps navigation out of the router so components
// still work where no App Router is mounted, which is every component test. A static export
// has no server to redirect anyway, so a plain assignment is the whole mechanism.
export function goTo(path: string): void {
  // Guarded because jsdom has no real navigation: a test asserts the state change, not the move.
  if (typeof window !== "undefined") window.location.assign(path);
}
