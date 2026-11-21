import { useT } from "@lila";
import { Button } from "../../components/ui";
import { AuthCard } from "../../components/Auth";

export default function InvalidToken() {
  const t = useT();
  return (
    <AuthCard title={t("invalid or expired token", "Invalid or expired link")}>
      <p className="mb-6 text-center text-sm text-muted-foreground">
        {t("your password reset link is invalid or has expired.", "Your password reset link is invalid or has expired.")}
      </p>
      <Button href="/forgot-password" className="w-full">{t("request new password reset link", "Request a new link")}</Button>
    </AuthCard>
  );
}
