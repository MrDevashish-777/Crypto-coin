import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/server/guard";
import { correlationId } from "@/lib/api/fetcher";
import { fetchUpstream, safeMustEnv } from "@/lib/server/upstream";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireAdmin();
  if (!auth.ok) return auth.response;

  const { id } = await params;
  const nestBaseEnv = safeMustEnv("NEST_API_BASE_URL");
  if (!nestBaseEnv.ok) return nestBaseEnv.response;
  const nestBase = nestBaseEnv.value;
  const internalApiKey = process.env.NEST_API_INTERNAL_API_KEY;
  const route = internalApiKey ? `/internal/signals/${id}` : `/signals/${id}`;
  const url = `${nestBase.replace(/\/$/, "")}${route}`;
  const headers: Record<string, string> = {
    "x-correlation-id": correlationId("signal-detail"),
  };
  if (internalApiKey) {
    headers["x-api-key"] = internalApiKey;
  } else {
    const jwtEnv = safeMustEnv("NEST_API_JWT");
    if (!jwtEnv.ok) return jwtEnv.response;
    headers.Authorization = `Bearer ${jwtEnv.value}`;
  }
  return fetchUpstream(
    url,
    {
      headers,
      cache: "no-store",
    },
    "nest",
  );
}

