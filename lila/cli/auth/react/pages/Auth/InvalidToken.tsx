import { Link, useT } from "@lila";
import { AuthCard } from "../../components/Auth";

export default function InvalidToken() {
  const t = useT();
  return (
    <AuthCard title={t("invalid or expired token", "Invalid or expired link")}>
      <p className="mb-6 text-center text-sm text-slate-500">
        {t("your password reset link is invalid or has expired.", "Your password reset link is invalid or has expired.")}
      </p>
      <Link href="/forgot-password" className="block w-full rounded-xl bg-blue-600 py-2.5 text-center text-sm font-semibold text-white">
        {t("request new password reset link", "Request a new link")}
      </Link>
    </AuthCard>
  );
}
