import NotesClient from "@/components/notes-client";

export default async function NotePage({ params }: { params: Promise<{ noteId: string }> }) {
  const { noteId } = await params;
  return <NotesClient noteId={noteId} />;
}

