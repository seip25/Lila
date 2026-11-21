import { Link, useForm, useT } from "@lila";
import { AuthCard, Field, FormMessage, Submit } from "../../components/Auth";

// POST /forgot-password {email} -> always the same answer (no account enumeration).
export default function ForgotPassword() {
  const t = useT();
  const form = useForm({ email: "" });
  return (
    <AuthCard title={t("recover_password", "Recover password")} subtitle={t("forgot_instruction", "We will email you a reset link")}>
      <form className="space-y-4" onSubmit={form.handleSubmit("/forgot-password", { reset: true })} noValidate>
        <FormMessage error={form.errors._form} message={form.message} />
        <Field label={t("email", "Email Address")} type="email" required autoComplete="email" {...form.field("email")} error={form.errors.email} />
        <Submit processing={form.processing}>{t("send", "Send")}</Submit>
        <p className="text-center text-xs">
          <Link href="/login" className="font-semibold text-blue-600 hover:underline dark:text-blue-400">{t("sign_in", "Sign In")}</Link>
        </p>
      </form>
    </AuthCard>
  );
}
