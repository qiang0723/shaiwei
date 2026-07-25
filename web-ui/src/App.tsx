import zhCN from "antd/locale/zh_CN";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { AppShell } from "./components/AppShell";
import { EvidenceProvider } from "./components/evidence";
import { PageLoading } from "./components/RequestState";
import { RouterProvider, useRouter } from "./routing";

const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const PaperPage = lazy(() => import("./pages/PaperPage"));
const SignalsPage = lazy(() => import("./pages/SignalsPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 0,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false
    }
  }
});

function styleNonce(): string {
  return (
    document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content ??
    "__P3_STYLE_NONCE_MISSING__"
  );
}

function RootRedirect() {
  const { location, navigate } = useRouter();
  useEffect(() => navigate(`/overview${location.search}`, { replace: true }), [location.search, navigate]);
  return <PageLoading label="正在进入总览…" />;
}

function NotFound() {
  return (
    <section className="request-error" role="alert">
      <div className="error-kicker">404</div>
      <h1>此只读页面未开放</h1>
      <p>当前 P3-1 只提供总览、模拟组合和股票池/信号。</p>
    </section>
  );
}

function AppRoutes() {
  const { location } = useRouter();
  let page;
  if (location.pathname === "/") page = <RootRedirect />;
  else if (location.pathname === "/overview") page = <OverviewPage />;
  else if (location.pathname === "/paper") page = <PaperPage />;
  else if (location.pathname === "/signals") page = <SignalsPage />;
  else page = <NotFound />;

  return <AppShell>{page}</AppShell>;
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      csp={{ nonce: styleNonce() }}
      theme={{
        token: {
          colorPrimary: "#174e72",
          colorInfo: "#174e72",
          colorSuccess: "#237a57",
          colorWarning: "#9a6300",
          colorError: "#b43b35",
          colorText: "#172532",
          colorTextSecondary: "#607080",
          colorBgLayout: "#f3f6f8",
          colorBorder: "#dce4e9",
          borderRadius: 10,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
        }
      }}
    >
      <QueryClientProvider client={queryClient}>
        <RouterProvider>
          <EvidenceProvider>
            <Suspense fallback={<PageLoading label="正在装载页面模块…" />}>
              <AppRoutes />
            </Suspense>
          </EvidenceProvider>
        </RouterProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
