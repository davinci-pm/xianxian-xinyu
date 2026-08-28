import NotesClient from "@/components/notes-client";

export default async function NotesPage({ searchParams }: { searchParams: Promise<{ conversation?: string }> }) {
  const { conversation } = await searchParams;
  return <NotesClient conversationId={conversation} />;
}

