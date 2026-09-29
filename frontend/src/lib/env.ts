const rawEnv = {
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
  VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY,
}

type EnvName = keyof typeof rawEnv

const missingNames = Object.entries(rawEnv)
  .filter(([, value]) => typeof value !== "string" || value.trim() === "")
  .map(([name]) => name)

if (missingNames.length > 0) {
  throw new Error(
    `Missing required frontend environment variables: ${missingNames.join(", ")}`,
  )
}

function requiredValue(name: EnvName): string {
  return rawEnv[name] as string
}

function requiredHttpUrl(name: EnvName): string {
  const value = requiredValue(name)
  let url: URL

  try {
    url = new URL(value)
  } catch {
    throw new Error(`${name} must be a valid absolute URL`)
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${name} must use http or https`)
  }

  return value.replace(/\/+$/, "")
}

export const env = Object.freeze({
  apiBaseUrl: requiredHttpUrl("VITE_API_BASE_URL"),
  supabaseUrl: requiredHttpUrl("VITE_SUPABASE_URL"),
  supabaseAnonKey: requiredValue("VITE_SUPABASE_ANON_KEY"),
})
