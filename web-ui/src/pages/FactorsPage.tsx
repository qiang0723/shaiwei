import { UiQueryError } from "../api";
import { PageError } from "../components/RequestState";
import { useRouter } from "../routing";
import { AdmissionsPage } from "./factors/AdmissionsPage";
import { CatalogPage } from "./factors/CatalogPage";
import { ComparePage } from "./factors/ComparePage";
import { DetailPage } from "./factors/DetailPage";

export default function FactorsPage() {
  const { location } = useRouter();
  if (location.pathname === "/factors") return <CatalogPage />;
  if (location.pathname === "/factors/compare") return <ComparePage />;
  const admission = location.pathname.match(/^\/factors\/([0-9a-f]{64})\/admissions$/);
  if (admission) return <AdmissionsPage factorId={admission[1]!} />;
  const detail = location.pathname.match(/^\/factors\/([0-9a-f]{64})$/);
  if (detail) return <DetailPage factorId={detail[1]!} />;
  return (
    <PageError
      error={new UiQueryError("INVALID_ARGUMENT", "因子页面路径无效")}
      retry={() => window.location.assign("/factors")}
    />
  );
}
