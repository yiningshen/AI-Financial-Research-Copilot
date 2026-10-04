import { useEffect, useState } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import type { Session } from "@supabase/supabase-js"

import { BrandMark } from "@/components/BrandMark"
import { Spinner } from "@/components/ui/spinner"
import { api, type AuthenticatedUser } from "@/lib/api"
import { ApiError } from "@/lib/http"
import { supabase } from "@/lib/supabase"
import { AuthPage } from "@/pages/AuthPage"
import { ChatPage } from "@/pages/ChatPage"

type BackendVerification = {
  accessToken: string
  user: AuthenticatedUser | null
  error: string | null
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [backendVerification, setBackendVerification] =
    useState<BackendVerification | null>(null)
  const [signOutError, setSignOutError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    void supabase.auth.getSession().then(({ data }) => {
      if (isMounted) {
        setSession(data.session)
        setIsLoading(false)
      }
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setIsLoading(false)
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  useEffect(() => {
    if (session === null) {
      return
    }

    let isCurrent = true
    const accessToken = session.access_token

    void api
      .getCurrentUser()
      .then((user) => {
        if (isCurrent) {
          setBackendVerification({ accessToken, user, error: null })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setBackendVerification({
            accessToken,
            user: null,
            error:
              error instanceof ApiError
                ? error.message
                : "Unable to verify your session.",
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [session])

  async function signOut() {
    setSignOutError(null)
    const { error } = await supabase.auth.signOut()
    if (error) {
      setSignOutError(error.message)
    }
  }

  if (isLoading) {
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-5 bg-background">
        <BrandMark />
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Spinner className="text-primary" />
          Loading your workspace…
        </p>
      </main>
    )
  }

  const verification = session
    ? backendVerification?.accessToken === session.access_token
      ? backendVerification
      : null
    : null

  const chatElement =
    session === null ? (
      <Navigate to="/login" replace />
    ) : verification === null ? (
      <main className="flex min-h-svh flex-col items-center justify-center gap-5 bg-background">
        <BrandMark />
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Spinner className="text-primary" />
          Verifying secure access…
        </p>
      </main>
    ) : verification.user === null ? (
      <main className="flex min-h-svh items-center justify-center bg-muted/40 px-4">
        <p className="text-sm text-destructive" role="alert">
          Backend authentication failed: {verification.error}
        </p>
      </main>
    ) : (
      <ChatPage
        email={verification.user.email ?? session.user.email ?? ""}
        signOutError={signOutError}
        onSignOut={signOut}
      />
    )

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            session === null ? <AuthPage /> : <Navigate to="/chats" replace />
          }
        />
        <Route
          path="/chats"
          element={chatElement}
        />
        <Route path="/chats/:threadId" element={chatElement} />
        <Route
          path="*"
          element={
            <Navigate to={session === null ? "/login" : "/chats"} replace />
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
