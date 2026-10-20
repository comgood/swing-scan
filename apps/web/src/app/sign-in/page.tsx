// Sign in (spec 0015). Client rendered, as a static export requires: there is no server here
// to hold a session or perform a redirect.
import { SignInRoute } from "@/features/auth";

export default function SignInPage() {
  return <SignInRoute />;
}
