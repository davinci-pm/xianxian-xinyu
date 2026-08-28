import PathsClient from "@/components/paths-client";

export default async function PathsPage({ searchParams }: { searchParams: Promise<{ concern?: string }> }) {
  const { concern = "" } = await searchParams;
  return <PathsClient initialConcern={concern.slice(0, 500)} />;
}

