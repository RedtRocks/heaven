import Chat from "@/components/Chat";

export const metadata = {
  title: "Memory Assistant - Keepsake",
};

export default function AssistantPage() {
  return (
    <div>
      <Chat endpoint="/assistant/chat" useFallback={true} />
    </div>
  );
}
