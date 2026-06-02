import { useState, type FormEvent } from "react";
import { CheckCircle2, CircleDot, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const REQUEST_URL = "/api/director/auth/request";

export function Login({ version }: { version: string }) {
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
    <div className="grid min-h-svh place-items-center px-5">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2">
            <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <CircleDot className="size-5" />
            </span>
            <span className="text-sm font-medium text-muted-foreground">AI Alpha Squad</span>
          </div>
          <CardTitle className="text-xl">Director Dashboard</CardTitle>
          <CardDescription>Sign in to view the squad dashboard.</CardDescription>
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="flex items-start gap-2 rounded-lg border border-brand-green-dim bg-brand-green/[0.08] p-4 text-sm">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-green" />
              <div>
                <p className="text-foreground">Check your inbox.</p>
                <p className="mt-1 text-muted-foreground">
                  If <span className="text-foreground">{email}</span> is authorized, a sign-in link
                  is on its way. It expires in 15 minutes.
                </p>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                <Label htmlFor="email" className="text-xs uppercase tracking-wide text-muted-foreground">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
              {error && <p className="text-sm text-brand-danger">{error}</p>}
              <Button type="submit" disabled={busy || !email}>
                <Mail className="h-4 w-4" />
                {busy ? "Sending…" : "Email me a sign-in link"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
      <p className="pointer-events-none fixed bottom-4 text-xs text-muted-foreground">v{version}</p>
    </div>
  );
}
