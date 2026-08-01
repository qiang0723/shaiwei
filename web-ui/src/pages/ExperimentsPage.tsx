import { UiQueryError } from "../api";
import { PageError } from "../components/RequestState";
import { useRouter } from "../routing";
import type { ExperimentKind } from "../types";
import { CatalogPage } from "./experiments/CatalogPage";
import { DetailPage } from "./experiments/DetailPage";

export default function ExperimentsPage() {
  const { location } = useRouter();
  if (location.pathname === "/experiments") return <CatalogPage />;
  const detail = location.pathname.match(
    /^\/experiments\/(research_experiment|p2_engineering_run|p2_effect_original|p2_effect_correction)\/([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/
  );
  if (detail) return <DetailPage kind={detail[1] as ExperimentKind} experimentId={detail[2]!} />;
  return (
    <PageError
      error={new UiQueryError("INVALID_ARGUMENT", "模型/回测页面路径无效")}
      retry={() => window.location.assign("/experiments")}
    />
  );
}
