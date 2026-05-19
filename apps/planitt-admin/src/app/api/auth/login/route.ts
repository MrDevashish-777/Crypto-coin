import { NextRequest, NextResponse } from "next/server";
import { isValidAdminCredentials, writeSession } from "@/lib/auth";

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { username?: string; password?: string };
    const username = (body.username || "").trim();
    const password = body.password || "";
    if (!isValidAdminCredentials(username, password)) {
      return NextResponse.json({ ok: false, error: "Invalid credentials" }, { status: 401 });
    }
    await writeSession(username);
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid payload" }, { status: 400 });
  }
}

