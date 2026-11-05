import {
  Database,
  FileBarChart,
  LayoutDashboard,
  LineChart,
  MessageSquare,
  Package,
  Settings,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react"
import { NavLink } from "react-router-dom"

import { APP_VERSION } from "@/lib/constants"
import { cn } from "@/lib/utils"

const GROUPS: { label: string; items: { to: string; label: string; icon: LucideIcon; end?: boolean }[] }[] = [
  {
    label: "Analytics",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/sales", label: "Sales", icon: LineChart },
      { to: "/customers", label: "Customers", icon: Users },
      { to: "/products", label: "Products", icon: Package },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/predictions", label: "Predictions", icon: TrendingUp },
      { to: "/assistant", label: "Assistant", icon: MessageSquare },
      { to: "/reports", label: "Reports", icon: FileBarChart },
    ],
  },
  {
    label: "Workspace",
    items: [
      { to: "/data", label: "Data", icon: Database },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
]

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <nav className="flex flex-col gap-5" aria-label="Primary">
        {GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{group.label}</p>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-muted-foreground transition hover:bg-sidebar-accent hover:text-foreground",
                        isActive && "bg-primary/15 font-medium text-foreground shadow-sm ring-1 ring-primary/25",
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      <p className="mt-auto px-3 pt-6 text-xs text-muted-foreground">InsightFlow {APP_VERSION}</p>
    </div>
  )
}
