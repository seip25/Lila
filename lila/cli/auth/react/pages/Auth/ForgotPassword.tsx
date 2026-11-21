import { Link, useT } from "@lila";
import { Form, FormMessage, Input, SubmitButton } from "../../components/ui";
import { AuthCard } from "../../components/Auth";

// POST /forgot-password {email} -> always the same answer (no account enumeration).
export default function ForgotPassword() {
  const t = useT();
  return (
    <AuthCard title={t("recover_password", "Recover password")} subtitle={t("forgot_instruction", "We will email you a reset link")}>
      <Form action="/forgot-password" initial={{ email: "" }} reset>
        <FormMessage />
        <Input name="email" type="email" label={t("email", "Email Address")} required autoComplete="email" />
        <SubmitButton loadingText={t("loading", "Loading...")}>{t("send", "Send")}</SubmitButton>
        <p className="text-center text-xs">
          <Link href="/login" className="lila-link font-semibold">{t("sign_in", "Sign In")}</Link>
        </p>
      </Form>
    </AuthCard>
  );
}
