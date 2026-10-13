import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toast";
import AuditLog from "./pages/AuditLog";
import EdgeNode from "./pages/EdgeNode";
import Incidents from "./pages/Incidents";
import Journeys from "./pages/Journeys";
import Overview from "./pages/Overview";
import Policies from "./pages/Policies";
import Scorecard from "./pages/Scorecard";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  // Order matters: the toast renders <Link>, so it must sit inside the router.
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ToastProvider>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<Overview />} />
                <Route path="incidents" element={<Incidents />} />
                <Route path="incidents/:id" element={<Incidents />} />
                <Route path="journeys" element={<Journeys />} />
                <Route path="edge" element={<EdgeNode />} />
                <Route path="policies" element={<Policies />} />
                <Route path="audit" element={<AuditLog />} />
                <Route path="scorecard" element={<Scorecard />} />
              </Route>
            </Routes>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
