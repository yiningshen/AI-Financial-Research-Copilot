import { createClient } from "@supabase/supabase-js"

import { env } from "@/lib/env"

export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    detectSessionInUrl: true,
    persistSession: true,
  },
})

export async function getAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.getSession()

  if (error) {
    throw error
  }
  if (data.session === null) {
    throw new Error("You must be signed in to continue.")
  }

  return data.session.access_token
}
