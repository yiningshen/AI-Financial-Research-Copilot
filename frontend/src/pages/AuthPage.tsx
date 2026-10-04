import { useState, type FormEvent } from "react"
import { CheckCircle2Icon, EyeIcon, EyeOffIcon, LockKeyholeIcon } from "lucide-react"

import { BrandMark } from "@/components/BrandMark"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { supabase } from "@/lib/supabase"

export function AuthPage() {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)

    const form = event.currentTarget
    const formData = new FormData(form)
    const email = String(formData.get("email")).trim()
    const password = String(formData.get("password"))

    const result = await supabase.auth.signInWithPassword({ email, password })

    setIsSubmitting(false)

    if (result.error) {
      setError(result.error.message)
      return
    }

    form.reset()
  }

  return (
    <main className="grid min-h-svh bg-background lg:grid-cols-[minmax(0,1.05fr)_minmax(440px,0.95fr)]">
      <section className="relative hidden overflow-hidden bg-primary p-12 text-primary-foreground lg:flex lg:flex-col">
        <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(to_right,rgba(255,255,255,.16)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,.16)_1px,transparent_1px)] [background-size:48px_48px]" />
        <div className="absolute -right-28 top-32 size-96 rounded-full bg-white/10 blur-3xl" />

        <BrandMark className="relative [&>span:first-child]:bg-white [&>span:first-child]:text-primary [&>span:last-child_span]:text-white/70 [&>span:last-child_span:first-child]:text-white" />

        <div className="relative my-auto max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-white/70">
            Evidence-first research
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-[-0.035em] xl:text-5xl">
            Move from filing to insight without losing the source.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-white/75">
            Search Driftwood&apos;s SEC corpus, compare disclosures, and verify every
            answer against the exact underlying passage.
          </p>
          <div className="mt-10 grid gap-4 text-sm text-white/85 sm:grid-cols-2">
            <p className="flex items-center gap-2">
              <CheckCircle2Icon className="size-4" aria-hidden="true" />
              Filing-level citations
            </p>
            <p className="flex items-center gap-2">
              <CheckCircle2Icon className="size-4" aria-hidden="true" />
              Grounded answers only
            </p>
          </div>
        </div>

        <p className="relative text-xs text-white/60">
          Internal research workspace · Authorized users only
        </p>
      </section>

      <section className="flex min-h-svh flex-col px-5 py-6 sm:px-10 lg:px-16">
        <BrandMark className="lg:hidden" />
        <div className="flex flex-1 items-center justify-center py-10">
          <Card className="w-full max-w-md border-0 bg-transparent shadow-none">
            <CardHeader className="px-0 pb-7">
              <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <LockKeyholeIcon className="size-5" aria-hidden="true" />
              </div>
              <CardTitle className="text-3xl tracking-[-0.025em]">
                Welcome back
              </CardTitle>
              <CardDescription className="text-sm leading-6">
                Sign in with your Driftwood Capital credentials to continue.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="space-y-2">
                  <Label htmlFor="email">Work email</Label>
                  <InputGroup>
                    <InputGroupInput
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      placeholder="analyst@driftwood.example"
                      required
                    />
                  </InputGroup>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <InputGroup>
                    <InputGroupInput
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      minLength={8}
                      required
                    />
                    <InputGroupAddon align="inline-end">
                      <InputGroupButton
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        onClick={() => setShowPassword((current) => !current)}
                        size="icon-xs"
                      >
                        {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                      </InputGroupButton>
                    </InputGroupAddon>
                  </InputGroup>
                </div>

                {error ? (
                  <p
                    className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
                    role="alert"
                  >
                    {error}
                  </p>
                ) : null}
                <Button className="h-11 w-full" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Spinner data-icon="inline-start" />
                      Signing in…
                    </>
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </form>
              <p className="mt-6 text-center text-xs leading-5 text-muted-foreground">
                Access is limited to approved Driftwood analysts.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  )
}
