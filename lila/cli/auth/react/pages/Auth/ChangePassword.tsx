import type { FormEvent } from "react";
import { Link, useForm, useT } from "@lila";
import { AuthCard, Field, FormMessage, Submit } from "../../components/Auth";

// GET /change-password/{token} (valid token) ; POST /change-password {token, new_password, confirm_password}
export default function ChangePassword({ token }: { token: string }) {
  const t = useT();
  const form = useForm({ token, new_password: "", confirm_password: "" });
  const done = Boolean(form.message);
  const submit = (event: FormEvent) => {
    if (form.data.new_password !== form.data.confirm_password) {
      event.preventDefault();
      form.setErrors({ confirm_password: t("passwords not match", "Passwords do not match") });
      return;
    }
    return form.handleSubmit("/change-password")(event);
  };
  return (
    <AuthCard title={t("reset_password", "Reset password")}>
      {done ? (
        <div className="space-y-4 text-center">
          <FormMessage message={form.message} />
          <Link href="/login" className="font-semibold text-blue-600 hover:underline">{t("sign_in", "Sign In")}</Link>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={submit} noValidate>
          <FormMessage error={form.errors._form} />
          <Field label={t("new_password", "New password")} type="password" required minLength={8} autoComplete="new-password" {...form.field("new_password")} error={form.errors.new_password} />
          <Field label={t("confirm_password", "Confirm password")} type="password" required minLength={8} autoComplete="new-password" {...form.field("confirm_password")} error={form.errors.confirm_password} />
          <Submit processing={form.processing}>{t("save", "Save")}</Submit>
        </form>
      )}
    </AuthCard>
  );
}
