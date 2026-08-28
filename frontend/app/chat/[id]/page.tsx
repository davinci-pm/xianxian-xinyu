import ChatClient from "@/components/chat-client";

export default async function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ChatClient conversationId={id} />;
}
