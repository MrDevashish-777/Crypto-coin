import { NextRequest } from "next/server";
import { requireAdmin } from "@/lib/server/guard";
import { correlationId } from "@/lib/api/fetcher";
import { fetchUpstream, safeMustEnv, useFastapiOperatorSource } from "@/lib/server/upstream";

export async function GET(req: NextRequest) {
  const auth = await requireAdmin();
  if (!auth.ok) return auth.response;

  const limit = req.nextUrl.searchParams.get("limit") || "20";

  if (useFastapiOperatorSource()) {
    const fastapiEnv = safeMustEnv("FASTAPI_BASE_URL");
    if (!fastapiEnv.ok) return fastapiEnv.response;
    const apiKeyEnv = safeMustEnv("FASTAPI_INTERNAL_API_KEY");
    if (!apiKeyEnv.ok) return apiKeyEnv.response;
    const fastapi = fastapiEnv.value.replace(/\/$/, "");
    const url = `${fastapi}/api/v1/news?limit=${encodeURIComponent(limit)}`;
    return fetchUpstream(
      url,
      {
        headers: {
          "x-api-key": apiKeyEnv.value,
          "x-correlation-id": correlationId("news"),
        },
        next: { revalidate: 20 },
      },
      "fastapi",
    );
  }

  const nestBaseEnv = safeMustEnv("NEST_API_BASE_URL");
  if (!nestBaseEnv.ok) return nestBaseEnv.response;
  const nestBase = nestBaseEnv.value.replace(/\/$/, "");
  const nestKey = safeMustEnv("NEST_API_INTERNAL_API_KEY");
  if (!nestKey.ok) return nestKey.response;

  const url = `${nestBase}/news?limit=${encodeURIComponent(limit)}`;
  return fetchUpstream(
    url,
    {
      headers: {
        "x-api-key": nestKey.value,
        "x-correlation-id": correlationId("news"),
      },
      next: { revalidate: 20 },
    },
    "nest",
  );
}
