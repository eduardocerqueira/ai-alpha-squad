import {
  CheckCircle2,
  CircleDot,
  Inbox,
  LogOut,
  Loader2,
  TriangleAlert,
} from "lucide-react";
import type { Dashboard } from "@/types";
import { GROUPS, jobsInGroup, type TabKey } from "@/lib/jobs";
import { cn } from "@/lib/utils";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const TAB_ICON: Record<TabKey, typeof Inbox> = {
  open: Inbox,
  in_progress: Loader2,
  blocked: TriangleAlert,
  done: CheckCircle2,
};

// Tabs whose count should glow amber/red because they want the Director.
const ALERT_TONE: Partial<Record<TabKey, string>> = {
  open: "text-brand-amber",
  blocked: "text-brand-danger",
};

export function AppSidebar({
  data,
  active,
  onSelect,
  email,
  repo,
  onSignOut,
}: {
  data: Dashboard | null;
  active: TabKey;
  onSelect: (key: TabKey) => void;
  email: string;
  repo: string;
  onSignOut: () => void;
}) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-1.5">
          <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <CircleDot className="size-5" />
          </span>
          <div className="grid flex-1 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-semibold">AI Alpha Squad</span>
            <span className="truncate text-xs text-muted-foreground">Director Dashboard</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Status</SidebarGroupLabel>
          <SidebarMenu>
            {GROUPS.map((g) => {
              const Icon = TAB_ICON[g.key];
              const count = jobsInGroup(data, g.key).length;
              const isActive = g.key === active;
              const tone = count > 0 ? ALERT_TONE[g.key] : undefined;
              return (
                <SidebarMenuItem key={g.key}>
                  <SidebarMenuButton
                    isActive={isActive}
                    tooltip={`${g.label} (${count})`}
                    onClick={() => onSelect(g.key)}
                  >
                    <Icon className={cn(tone)} />
                    <span className="flex-1">{g.label}</span>
                    <span className={cn("tabular-nums text-xs text-sidebar-foreground/70", tone)}>
                      {count}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
        <div className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          <span className="font-mono">{repo}</span>
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton size="lg" tooltip={email}>
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg uppercase">
                      {email.slice(0, 2)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">Signed in</span>
                    <span className="truncate text-xs text-muted-foreground">{email}</span>
                  </div>
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-[--radix-popper-anchor-width] min-w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="grid text-sm">
                    <span className="font-medium">Director</span>
                    <span className="truncate text-xs text-muted-foreground">{email}</span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onSignOut} className="text-brand-danger focus:text-brand-danger">
                  <LogOut className="size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
