import Chat from "@/components/Chat";

export const metadata = {
  title: "Memory Assistant - Keepsake",
};

export default function AssistantPage() {
  return (
    <div className="h-screen">
      <Chat endpoint="/assistant/chat" />
    </div>
  );
}
