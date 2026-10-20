// Accounts (spec 0015). The presentational form is exported for the `/ui` gallery, which
// mounts sections with no QueryClient; the routes and the header status are connected.
export { AuthForm, LOCAL_ONLY, PASSWORD_MIN, PURPOSE, type AuthFormProps } from "./auth-form";
export { AccountRoute, DELETE_WARNING } from "./account-route";
export { AccountStatus } from "./account-status";
export { goTo } from "./navigate";
export {
  AccountsNotHere,
  NOT_HERE_BODY,
  NOT_HERE_TITLE,
  RegisterRoute,
  SignInRoute,
} from "./auth-routes";
export {
  CredentialsRejectedError,
  ME_KEY,
  useDeleteAccount,
  useLogin,
  useLogout,
  useMe,
  useRegister,
} from "./queries";
