import type { FormEvent } from "react";
import { Link, useForm, useT } from "@lila";
import { AuthCard, Field, FormMessage, OAuthButtons, Submit, type Provider } from "../../components/Auth";

// POST /register (RegisterModel: name, email, password, password_2)
export default function Register({ providers = [] }: { providers: Provider[] }) {
  const t = useT();
  const form = useForm({ name: "", email: "", password: "", password_2: "" });
  const submit = (event: FormEvent) => {
    if (form.data.password !== form.data.password_2) {
      event.preventDefault();
      form.setErrors({ password_2: t("passwords not match", "Passwords do not match") });
      return;
    }
    return form.handleSubmit("/register", { redirect: "/dashboard" })(event);
  };
  return (
    <AuthCard title={t("register", "Create account")} subtitle={t("register_desc", "Join in a few seconds")}>
      <OAuthButtons providers={providers} />
      <form className="space-y-4" onSubmit={submit} noValidate>
        <FormMessage error={form.errors._form} />
        <Field label={t("full_name", "Full name")} required minLength={2} maxLength={50} autoComplete="name" {...form.field("name")} error={form.errors.name} />
        <Field label={t("email", "Email Address")} type="email" required autoComplete="email" {...form.field("email")} error={form.errors.email} />
        <Field label={t("password", "Password")} type="password" required minLength={8} autoComplete="new-password" {...form.field("password")} error={form.errors.password} />
        <Field label={t("confirm_password", "Confirm password")} type="password" required minLength={8} autoComplete="new-password" {...form.field("password_2")} error={form.errors.password_2} />
        <Submit processing={form.processing}>{t("register", "Create account")}</Submit>
        <p className="mt-4 border-t border-slate-100 pt-3 text-center text-xs text-slate-500 dark:border-slate-800">
          {t("already_have_account", "Already have an account?")}{" "}
          <Link href="/login" className="font-semibold text-blue-600 hover:underline dark:text-blue-400">{t("sign_in", "Sign In")}</Link>
        </p>
      </form>
    </AuthCard>
  );
}
