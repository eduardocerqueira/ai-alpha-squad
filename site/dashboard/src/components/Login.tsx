import { useState, type FormEvent } from "react";
import { CheckCircle2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

const REQUEST_URL = "/api/director/auth/request";

export function Login() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(REQUEST_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error("Request failed. Try again shortly.");
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-[70vh] place-items-center px-5">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6">
        <h1 className="text-xl font-semibold tracking-tight">Director</h1>
        <p className="mt-1 text-sm text-muted">Sign in to view the squad dashboard.</p>

        {sent ? (
          <div className="mt-6 flex items-start gap-2 rounded-lg border border-[var(--green-dim)] bg-[color:rgba(34,197,94,0.08)] p-4 text-sm">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green" />
            <div>
              <p className="text-text">Check your inbox.</p>
              <p className="mt-1 text-muted">
                If <span className="text-text">{email}</span> is authorized, a sign-in link is on
                its way. It expires in 15 minutes.
              </p>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 flex flex-col gap-3">
            <label className="text-xs font-medium uppercase tracking-wide text-muted" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="h-10 rounded-md border border-border bg-bg px-3 text-sm text-text outline-none focus:border-green"
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" variant="primary" disabled={busy || !email}>
              <Mail className="h-4 w-4" />
              {busy ? "Sending…" : "Email me a sign-in link"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
