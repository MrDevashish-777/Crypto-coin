import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/server/guard";
import { correlationId } from "@/lib/api/fetcher";
import { getAdminDeploymentMode, safeMustEnv, useFastapiOperatorSource } from "@/lib/server/upstream";

async function statusCheck(url: string, headers?: Record<string, string>) {
  try {
    const res = await fetch(url, { headers, cache: "no-store" });
    return { ok: res.ok, status: res.status };
  } catch {
    return { ok: false, status: 0 };
  }
}

export async function GET() {
  const auth = await requireAdmin();
  if (!auth.ok) return auth.response;

  const nestBaseEnv = safeMustEnv("NEST_API_BASE_URL");
  if (!nestBaseEnv.ok) return nestBaseEnv.response;

  const nestBase = nestBaseEnv.value.replace(/\/$/, "");
  const nestInternalApiKey = process.env.NEST_API_INTERNAL_API_KEY;
  const corr = correlationId("health");
  const nestPath = nestInternalApiKey ? "/internal/performance" : "/performance";
  const nestHeaders: Record<string, string> = { "x-correlation-id": corr };
  if (nestInternalApiKey) {
    nestHeaders["x-api-key"] = nestInternalApiKey;
  } else {
    const jwtEnv = safeMustEnv("NEST_API_JWT");
    if (!jwtEnv.ok) {
      return NextResponse.json(
        {
          checked_at: new Date().toISOString(),
          status: "misconfigured",
          missing_env_vars: ["NEST_API_JWT"],
          hint: "Set NEST_API_INTERNAL_API_KEY or provide NEST_API_JWT in Netlify.",
        },
        { status: 500 },
      );
    }
    nestHeaders.Authorization = `Bearer ${jwtEnv.value}`;
  }

  const nest = await statusCheck(`${nestBase}${nestPath}`, nestHeaders);

  const operatorSource = useFastapiOperatorSource() ? "fastapi" : "nest";
  let news: { ok: boolean; status: number } = { ok: false, status: 503 };
  let market: { ok: boolean; status: number } = { ok: false, status: 503 };

  if (operatorSource === "fastapi") {
    const fastapiEnv = safeMustEnv("FASTAPI_BASE_URL");
    if (!fastapiEnv.ok) return fastapiEnv.response;
    const fastapiKeyEnv = safeMustEnv("FASTAPI_INTERNAL_API_KEY");
    if (!fastapiKeyEnv.ok) return fastapiKeyEnv.response;
    const fastapi = fastapiEnv.value.replace(/\/$/, "");
    const fastapiKey = fastapiKeyEnv.value;
    [news, market] = await Promise.all([
      statusCheck(`${fastapi}/api/v1/news?limit=1`, {
        "x-api-key": fastapiKey,
        "x-correlation-id": corr,
      }),
      statusCheck(`${fastapi}/api/v1/signals/market/status`, {
        "x-api-key": fastapiKey,
        "x-correlation-id": corr,
      }),
    ]);
  } else {
    if (!nestInternalApiKey) {
      return NextResponse.json(
        {
          checked_at: new Date().toISOString(),
          status: "misconfigured",
          missing_env_vars: ["NEST_API_INTERNAL_API_KEY"],
          hint: "Set NEST_API_INTERNAL_API_KEY so Nest /news and /market-status can be checked.",
        },
        { status: 500 },
      );
    }
    const newsCorr = correlationId("news");
    const marketCorr = correlationId("market");
    news = await statusCheck(`${nestBase}/news`, {
      "x-api-key": nestInternalApiKey,
      "x-correlation-id": newsCorr,
    });
    market = await statusCheck(`${nestBase}/market-status`, {
      "x-api-key": nestInternalApiKey,
      "x-correlation-id": marketCorr,
    });
  }

  let fast: { ok: boolean; status: number } = { ok: false, status: 0 };
  const fastapiUrl = process.env.FASTAPI_BASE_URL?.trim();
  if (fastapiUrl) {
    fast = await statusCheck(`${fastapiUrl.replace(/\/$/, "")}/health`);
  }

  return NextResponse.json({
    checked_at: new Date().toISOString(),
    deployment_mode: getAdminDeploymentMode(),
    operator_source: operatorSource,
    services: {
      nest_api: nest,
      fastapi_health: fast,
      news,
      market_status: market,
    },
  });
}
