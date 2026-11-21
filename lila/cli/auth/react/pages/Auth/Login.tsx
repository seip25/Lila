import { Link, useForm, useT } from "@lila";
import { AuthCard, Field, FormMessage, OAuthButtons, Submit, type Provider } from "../../components/Auth";

// GET /login -> react_render(request, "Auth/Login", {"providers": [...]})
// POST /login (LoginModel) -> {"success", "msg"} + session cookie
export default function Login({ providers = [] }: { providers: Provider[] }) {
  const t = useT();
  const form = useForm({ email: "", password: "" });
  return (
    <AuthCard title={t("login", "Welcome Back")} subtitle={t("sign_in_desc", "Sign in to your account")}>
      <OAuthButtons providers={providers} />
      <form className="space-y-4" onSubmit={form.handleSubmit("/login", { redirect: "/dashboard" })} noValidate>
        <FormMessage error={form.errors._form} />
        <Field label={t("email", "Email Address")} type="email" required autoComplete="email" placeholder="you@example.com" {...form.field("email")} error={form.errors.email} />
        <Field
          label={t("password", "Password")}
          type="password"
          required
          autoComplete="current-password"
          placeholder="••••••••"
          {...form.field("password")}
          error={form.errors.password}
          aside={<Link href="/forgot-password" className="text-xs text-blue-600 hover:underline dark:text-blue-400">{t("forgot your password", "Forgot password?")}</Link>}
        />
        <Submit processing={form.processing}>{t("sign_in", "Sign In")}</Submit>
        <p className="mt-4 border-t border-slate-100 pt-3 text-center text-xs text-slate-500 dark:border-slate-800">
          {t("dont_have_account", "Don't have an account?")}{" "}
          <Link href="/register" className="font-semibold text-blue-600 hover:underline dark:text-blue-400">{t("create account", "Create account")}</Link>
        </p>
      </form>
    </AuthCard>
  );
}
