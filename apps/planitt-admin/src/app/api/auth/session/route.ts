import { NextResponse } from "next/server";
import { readSession } from "@/lib/auth";

export async function GET() {
  const session = await readSession();
  return NextResponse.json({ authenticated: Boolean(session), session });
}

