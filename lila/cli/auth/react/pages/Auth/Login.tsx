import { Link, useT } from "@lila";
import { Form, Input, SubmitButton } from "../../components/ui";
import { AuthCard, nextUrl, OAuthButtons, type Provider } from "../../components/Auth";

// GET /login -> react_render(request, "Auth/Login", {"providers": [...]})
// POST /login (LoginModel) -> {"success", "msg"} + session cookie
export default function Login({ providers = [] }: { providers: Provider[] }) {
  const t = useT();
  return (
    <AuthCard title={t("login", "Welcome Back")} subtitle={t("sign_in_desc", "Sign in to your account")}>
      <OAuthButtons providers={providers} />
      <Form action="/login" initial={{ email: "", password: "" }} redirect={nextUrl("/dashboard")}>
        <Input name="email" type="email" label={t("email", "Email Address")} required autoComplete="email" placeholder="you@example.com" />
        <Input
          name="password"
          type="password"
          label={t("password", "Password")}
          required
          autoComplete="current-password"
          placeholder="••••••••"
          aside={<Link href="/forgot-password" className="lila-link text-xs">{t("forgot your password", "Forgot password?")}</Link>}
        />
        <SubmitButton loadingText={t("loading", "Loading...")}>{t("sign_in", "Sign In")}</SubmitButton>
        <p className="border-t border-border pt-3 text-center text-xs text-muted-foreground">
          {t("dont_have_account", "Don't have an account?")}{" "}
          <Link href="/register" className="lila-link font-semibold">{t("create account", "Create account")}</Link>
        </p>
      </Form>
    </AuthCard>
  );
}
