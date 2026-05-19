import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/server/guard";
import { correlationId } from "@/lib/api/fetcher";
import {
  fetchUpstream,
  isPublicNestOnlyMode,
  localOnlyFeatureDisabledResponse,
  safeMustEnv,
} from "@/lib/server/upstream";

export async function POST(req: NextRequest) {
  const auth = await requireAdmin();
  if (!auth.ok) return auth.response;
  if (isPublicNestOnlyMode()) return localOnlyFeatureDisabledResponse("generate");

  const body = (await req.json()) as { symbol?: string; timeframe?: string; strategy?: string };
  const symbol = (body.symbol || "").trim();
  const timeframe = (body.timeframe || "").trim();
  const strategy = (body.strategy || "planitt").trim();
  if (!symbol || !timeframe) {
    return NextResponse.json({ error: "symbol and timeframe are required" }, { status: 400 });
  }

  const fastapiEnv = safeMustEnv("FASTAPI_BASE_URL");
  if (!fastapiEnv.ok) return fastapiEnv.response;
  const apiKeyEnv = safeMustEnv("FASTAPI_INTERNAL_API_KEY");
  if (!apiKeyEnv.ok) return apiKeyEnv.response;
  const fastapi = fastapiEnv.value.replace(/\/$/, "");
  const apiKey = apiKeyEnv.value;
  const url = `${fastapi}/api/v1/signals/generate?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(
    timeframe,
  )}&strategy=${encodeURIComponent(strategy)}`;

  return fetchUpstream(
    url,
    {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "x-correlation-id": correlationId("generate"),
      },
      cache: "no-store",
    },
    "fastapi",
  );
}

