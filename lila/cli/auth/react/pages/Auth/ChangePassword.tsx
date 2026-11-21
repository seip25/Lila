import { Link, useForm, useT } from "@lila";
import { Form, FormMessage, Input, SubmitButton } from "../../components/ui";
import { AuthCard } from "../../components/Auth";

// GET /change-password/{token} (valid token) ; POST /change-password {token, new_password, confirm_password}
export default function ChangePassword({ token }: { token: string }) {
  const t = useT();
  const form = useForm({ token, new_password: "", confirm_password: "" });
  return (
    <AuthCard title={t("reset_password", "Reset password")}>
      {form.message ? (
        <div className="space-y-4 text-center">
          <p role="status" className="rounded-xl bg-success/10 px-4 py-2 text-sm text-success">{form.message}</p>
          <Link href="/login" className="lila-link font-semibold">{t("sign_in", "Sign In")}</Link>
        </div>
      ) : (
        <Form
          form={form}
          action="/change-password"
          initial={form.data}
          validate={(data) => ({ confirm_password: data.new_password !== data.confirm_password ? t("passwords not match", "Passwords do not match") : undefined })}
        >
          <FormMessage />
          <Input name="new_password" type="password" label={t("new_password", "New password")} required minLength={8} autoComplete="new-password" />
          <Input name="confirm_password" type="password" label={t("confirm_password", "Confirm password")} required minLength={8} autoComplete="new-password" />
          <SubmitButton>{t("save", "Save")}</SubmitButton>
        </Form>
      )}
    </AuthCard>
  );
}
