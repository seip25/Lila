import { useForm, useT, visit } from "@lila";
import { useState, type ReactElement } from "react";
import AppShell from "../../components/AppShell";
import type { SessionUser } from "../../components/Auth";
import { Button, Card, Form, Input, Modal, SubmitButton, toast } from "../../components/ui";

// POST /profile (UpdateProfileModel) and POST /delete-account (DeleteAccountModel)
export default function Profile({ user }: { user: SessionUser }) {
  const t = useT();
  const form = useForm({ name: user.name || "", password: "", password_2: "" });
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <Card title={t("profile", "Profile")}>
        <Form
          form={form}
          action="/profile"
          initial={form.data}
          className="max-w-lg"
          successToast
          // password_2 is optional: send null instead of "" (min_length=8).
          transform={(data) => ({ ...data, password_2: data.password_2 || null })}
          onSuccess={() => {
            form.setData("password", "");
            form.setData("password_2", "");
            // Reload the props (new name in the header) keeping this page state.
            visit("/profile", { replace: true, preserveScroll: true });
          }}
        >
          <Input name="name" label={t("name", "Name")} required minLength={2} maxLength={50} />
          <Input label={t("email", "Email")} value={user.email} disabled readOnly />
          <Input name="password_2" type="password" label={`${t("new_password", "New password")} (${t("optional", "optional")})`} minLength={8} autoComplete="new-password" />
          <Input name="password" type="password" label={`${t("password", "Password")} (${t("current", "current")})`} required autoComplete="current-password" />
          <SubmitButton className="w-auto">{t("save", "Save")}</SubmitButton>
        </Form>
      </Card>

      <Card title={<span className="text-danger">{t("danger_zone", "Danger zone")}</span>}
        description={t("once_you_delete_your_account_there_is_no_going_back", "Once you delete your account, there is no going back.")}>
        <Button variant="danger" onClick={() => setConfirming(true)}>{t("delete account", "Delete account")}</Button>
      </Card>

      <Modal open={confirming} onClose={() => setConfirming(false)} title={t("delete account", "Delete account")} size="sm">
        <Form
          action="/delete-account"
          initial={{ password: "" }}
          onSuccess={(data) => {
            toast.success(data?.msg || data?.message || "OK");
            visit("/login", { replace: true });
          }}
        >
          <Input name="password" type="password" label={t("password", "Password")} required autoComplete="current-password" />
          <SubmitButton variant="danger">{t("delete account", "Delete account")}</SubmitButton>
        </Form>
      </Modal>
    </>
  );
}

Profile.layout = (page: ReactElement<{ user: SessionUser }>) => <AppShell user={page.props.user}>{page}</AppShell>;
