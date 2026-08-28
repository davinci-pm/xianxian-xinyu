import { redirect } from "next/navigation";

export default async function PersonaPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  redirect(`/figures/${slug}`);
}
