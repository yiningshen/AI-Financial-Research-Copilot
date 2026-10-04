import { Link } from "react-router-dom"
import {
  ChevronsUpDownIcon,
  LogOutIcon,
  MessageSquareTextIcon,
  PlusIcon,
} from "lucide-react"

import { BrandMark } from "@/components/BrandMark"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import type { ChatThread } from "@/lib/api"

type ThreadSidebarProps = {
  threads: ChatThread[]
  activeThreadId?: string
  email: string
  isLoading: boolean
  isCreating: boolean
  error: string | null
  signOutError: string | null
  onCreate: () => void
  onRetry: () => void
  onSignOut: () => Promise<void>
}

type ThreadGroup = {
  label: string
  threads: ChatThread[]
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime()
}

function groupThreads(threads: ChatThread[]): ThreadGroup[] {
  const today = startOfDay(new Date())
  const groups: ThreadGroup[] = [
    { label: "Today", threads: [] },
    { label: "Previous 7 days", threads: [] },
    { label: "Earlier", threads: [] },
  ]

  for (const thread of threads) {
    const ageInDays = Math.floor(
      (today - startOfDay(new Date(thread.updated_at))) / 86_400_000,
    )
    const group = ageInDays <= 0 ? groups[0] : ageInDays <= 7 ? groups[1] : groups[2]
    group.threads.push(thread)
  }

  return groups.filter((group) => group.threads.length > 0)
}

function userInitials(email: string) {
  const name = email.split("@")[0]
  const parts = name.split(/[._-]/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "DC"
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  email,
  isLoading,
  isCreating,
  error,
  signOutError,
  onCreate,
  onRetry,
  onSignOut,
}: ThreadSidebarProps) {
  const { setOpenMobile } = useSidebar()
  const groups = groupThreads(threads)

  return (
    <Sidebar collapsible="icon" className="border-r-0">
      <SidebarHeader className="gap-3 border-b border-sidebar-border p-3">
        <Link
          className="rounded-lg px-1 py-0.5 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          to="/chats"
          onClick={() => setOpenMobile(false)}
        >
          <BrandMark className="group-data-[collapsible=icon]:[&>span:last-child]:hidden" />
        </Link>
        <Button
          className="w-full justify-start gap-2 group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:px-0"
          disabled={isCreating}
          onClick={onCreate}
        >
          <PlusIcon aria-hidden="true" />
          <span className="group-data-[collapsible=icon]:hidden">
            {isCreating ? "Creating…" : "New research"}
          </span>
        </Button>
      </SidebarHeader>

      <SidebarContent>
        {isLoading ? (
          <SidebarGroup>
            <SidebarGroupLabel>Recent conversations</SidebarGroupLabel>
            <SidebarMenu>
              {Array.from({ length: 5 }).map((_, index) => (
                <SidebarMenuItem key={index}>
                  <SidebarMenuSkeleton showIcon />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ) : error ? (
          <SidebarGroup>
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 group-data-[collapsible=icon]:hidden">
              <p className="text-xs leading-5 text-destructive" role="alert">
                {error}
              </p>
              <Button className="mt-1 h-auto px-0 text-xs" variant="link" onClick={onRetry}>
                Try again
              </Button>
            </div>
          </SidebarGroup>
        ) : groups.length === 0 ? (
          <SidebarGroup>
            <div className="px-2 py-6 text-center group-data-[collapsible=icon]:hidden">
              <MessageSquareTextIcon className="mx-auto size-5 text-muted-foreground/60" />
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Your research conversations will appear here.
              </p>
            </div>
          </SidebarGroup>
        ) : (
          groups.map((group) => (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.threads.map((thread) => (
                    <SidebarMenuItem key={thread.id}>
                      <SidebarMenuButton
                        asChild
                        isActive={activeThreadId === thread.id}
                        tooltip={thread.title ?? "Untitled research"}
                      >
                        <Link
                          to={`/chats/${thread.id}`}
                          onClick={() => setOpenMobile(false)}
                        >
                          <MessageSquareTextIcon aria-hidden="true" />
                          <span>{thread.title ?? "Untitled research"}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-2">
        {signOutError ? (
          <p className="px-2 py-1 text-xs text-destructive group-data-[collapsible=icon]:hidden" role="alert">
            {signOutError}
          </p>
        ) : null}
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton size="lg" tooltip={email}>
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-primary/10 text-xs font-semibold text-primary">
                      {userInitials(email)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">Analyst account</span>
                    <span className="block truncate text-xs text-muted-foreground">{email}</span>
                  </span>
                  <ChevronsUpDownIcon className="ml-auto" aria-hidden="true" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="min-w-64" side="right" align="end" sideOffset={8}>
                <DropdownMenuLabel>
                  <span className="block text-xs font-normal text-muted-foreground">Signed in as</span>
                  <span className="mt-0.5 block truncate text-sm text-foreground">{email}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => void onSignOut()}>
                  <LogOutIcon aria-hidden="true" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
