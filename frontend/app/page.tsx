import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COOKIE } from "@/lib/env";

export default async function RootPage() {
  const jar = await cookies();
  redirect(jar.get(COOKIE.accessToken) ? "/dashboard" : "/login");
}
