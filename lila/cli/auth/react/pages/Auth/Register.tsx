import { Link, useT } from "@lila";
import { Form, Input, SubmitButton } from "../../components/ui";
import { AuthCard, nextUrl, OAuthButtons, type Provider } from "../../components/Auth";

// POST /register (RegisterModel: name, email, password, password_2)
export default function Register({ providers = [] }: { providers: Provider[] }) {
  const t = useT();
  return (
    <AuthCard title={t("register", "Create account")} subtitle={t("register_desc", "Join in a few seconds")}>
      <OAuthButtons providers={providers} />
      <Form
        action="/register"
        initial={{ name: "", email: "", password: "", password_2: "" }}
        redirect={nextUrl("/dashboard")}
        validate={(data) => ({ password_2: data.password !== data.password_2 ? t("passwords not match", "Passwords do not match") : undefined })}
      >
        <Input name="name" label={t("full_name", "Full name")} required minLength={2} maxLength={50} autoComplete="name" />
        <Input name="email" type="email" label={t("email", "Email Address")} required autoComplete="email" />
        <Input name="password" type="password" label={t("password", "Password")} required minLength={8} autoComplete="new-password" />
        <Input name="password_2" type="password" label={t("confirm_password", "Confirm password")} required minLength={8} autoComplete="new-password" />
        <SubmitButton loadingText={t("loading", "Loading...")}>{t("register", "Create account")}</SubmitButton>
        <p className="border-t border-border pt-3 text-center text-xs text-muted-foreground">
          {t("already_have_account", "Already have an account?")}{" "}
          <Link href="/login" className="lila-link font-semibold">{t("sign_in", "Sign In")}</Link>
        </p>
      </Form>
    </AuthCard>
  );
}
