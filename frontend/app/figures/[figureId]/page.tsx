import PersonaDetailClient from "@/components/persona-detail-client";

export default async function FigurePage({ params, searchParams }: { params: Promise<{ figureId: string }>; searchParams: Promise<{ concern?: string }> }) {
  const [{ figureId }, { concern = "" }] = await Promise.all([params, searchParams]);
  return <PersonaDetailClient slug={figureId} initialConcern={concern.slice(0, 500)} />;
}

