import { QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import { AppShell } from "@/components/layout/AppShell"
import { GuestOnly, RequireAuth } from "@/components/layout/RequireAuth"
import { AuthProvider } from "@/contexts/auth-context"
import { ThemeProvider } from "@/contexts/theme-context"
import { WorkspaceProvider } from "@/contexts/workspace-context"
import { queryClient } from "@/lib/query-client"
import { AssistantPage } from "@/pages/Assistant"
import { CustomerAnalyticsPage } from "@/pages/CustomerAnalytics"
import { DataManagementPage } from "@/pages/DataManagement"
import { LoginPage } from "@/pages/Login"
import { NotFoundPage } from "@/pages/NotFound"
import { OverviewPage } from "@/pages/Overview"
import { PredictiveInsightsPage } from "@/pages/PredictiveInsights"
import { ProductAnalyticsPage } from "@/pages/ProductAnalytics"
import { RegisterPage } from "@/pages/Register"
import { ReportsPage } from "@/pages/Reports"
import { SalesAnalyticsPage } from "@/pages/SalesAnalytics"
import { SettingsPage } from "@/pages/Settings"

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <WorkspaceProvider>
              <Routes>
                <Route element={<GuestOnly />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                </Route>
                <Route element={<RequireAuth />}>
                  <Route element={<AppShell />}>
                    <Route index element={<OverviewPage />} />
                    <Route path="/data" element={<DataManagementPage />} />
                    <Route path="/sales" element={<SalesAnalyticsPage />} />
                    <Route path="/customers" element={<CustomerAnalyticsPage />} />
                    <Route path="/products" element={<ProductAnalyticsPage />} />
                    <Route path="/predictions" element={<PredictiveInsightsPage />} />
                    <Route path="/assistant" element={<AssistantPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                  </Route>
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </WorkspaceProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
