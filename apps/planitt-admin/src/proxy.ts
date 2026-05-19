import { NextRequest, NextResponse } from "next/server";
import { verifySessionToken } from "@/lib/auth";

export function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname;
  const isDashboard = path.startsWith("/dashboard");
  const isAuthApi = path.startsWith("/api/auth");
  const isLogin = path.startsWith("/login");

  if (!isDashboard && !isAuthApi && !isLogin) return NextResponse.next();

  const token = req.cookies.get("planitt_admin_session")?.value;
  const session = verifySessionToken(token);

  if (isDashboard && !session) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  if (isLogin && session) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/api/auth/:path*"],
};
