import { redirect } from "next/navigation";
import { readSession } from "@/lib/auth";
import { AdminShell } from "@/components/admin-shell";

export default async function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await readSession();
  if (!session) {
    redirect("/login");
  }
  return <AdminShell>{children}</AdminShell>;
}

