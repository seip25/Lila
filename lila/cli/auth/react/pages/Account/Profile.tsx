import { useForm, useT, visit } from "@lila";
import { useState, type ReactElement } from "react";
import AppShell from "../../components/AppShell";
import { Field, FormMessage, Submit, type SessionUser } from "../../components/Auth";

// POST /profile (UpdateProfileModel) and POST /delete-account (DeleteAccountModel)
export default function Profile({ user }: { user: SessionUser }) {
  const t = useT();
  const form = useForm({ name: user.name || "", password: "", password_2: "" });
  const remove = useForm({ password: "" });
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <section className="rounded-2xl border border-slate-200 bg-white p-8 dark:border-slate-800 dark:bg-slate-900">
        <h1 className="mb-6 text-2xl font-black">{t("profile", "Profile")}</h1>
        <form
          className="max-w-lg space-y-4"
          noValidate
          onSubmit={form.handleSubmit("/profile", {
            // password_2 is optional: send null instead of "" (min_length=8).
            transform: (data) => ({ ...data, password_2: data.password_2 || null }),
            // Reload the props (new name in the header) keeping this page state.
            onSuccess: () => { form.setData("password", ""); visit("/profile", { replace: true, preserveScroll: true }); },
          })}
        >
          <FormMessage error={form.errors._form} message={form.message} />
          <Field label={t("name", "Name")} required minLength={2} maxLength={50} {...form.field("name")} error={form.errors.name} />
          <Field label={t("email", "Email")} value={user.email} disabled readOnly />
          <Field label={`${t("new_password", "New password")} (${t("optional", "optional")})`} type="password" minLength={8} autoComplete="new-password" {...form.field("password_2")} error={form.errors.password_2} />
          <Field label={`${t("password", "Password")} (${t("current", "current")})`} type="password" required autoComplete="current-password" {...form.field("password")} error={form.errors.password} />
          <Submit processing={form.processing}>{t("save", "Save")}</Submit>
        </form>
      </section>

      <section className="rounded-2xl border border-red-200 bg-white p-8 dark:border-red-900/50 dark:bg-slate-900">
        <h2 className="mb-2 text-lg font-bold text-red-600">{t("danger_zone", "Danger zone")}</h2>
        <p className="mb-4 text-sm text-slate-500">
          {t("once_you_delete_your_account_there_is_no_going_back", "Once you delete your account, there is no going back.")}
        </p>
        {confirming ? (
          <form
            className="max-w-lg space-y-3"
            noValidate
            onSubmit={remove.handleSubmit("/delete-account", { onSuccess: () => visit("/login", { replace: true }) })}
          >
            <FormMessage error={remove.errors._form} />
            <Field label={t("password", "Password")} type="password" required autoComplete="current-password" {...remove.field("password")} error={remove.errors.password} />
            <button type="submit" disabled={remove.processing} className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {t("delete account", "Delete account")}
            </button>
          </form>
        ) : (
          <button onClick={() => setConfirming(true)} className="rounded-xl border border-red-600 px-4 py-2 text-sm font-semibold text-red-600">
            {t("delete account", "Delete account")}
          </button>
        )}
      </section>
    </>
  );
}

Profile.layout = (page: ReactElement<{ user: SessionUser }>) => <AppShell user={page.props.user}>{page}</AppShell>;
