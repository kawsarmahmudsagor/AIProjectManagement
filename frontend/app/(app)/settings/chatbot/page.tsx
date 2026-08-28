import { ChatbotProviderSelect } from "@/components/settings/chatbot-provider-select";
import { PreemptiveSuggestionsToggle } from "@/components/settings/preemptive-suggestions-toggle";
import { serverApiFetch } from "@/lib/server-api";
import type { ChatProvider, UserOut } from "@/lib/types";

export default async function ChatbotSettingsPage() {
  let chatProvider: ChatProvider = "gemini";
  let preemptiveSuggestions = false;
  try {
    const me = await serverApiFetch<UserOut>("auth/me");
    chatProvider = me.chat_provider;
    preemptiveSuggestions = me.chatbot_preemptive_github_suggestions;
  } catch {
    // backend not reachable yet — cards still render with defaults
  }

  return (
    <div className="grid max-w-2xl gap-6">
      <ChatbotProviderSelect initial={chatProvider} />
      <PreemptiveSuggestionsToggle initial={preemptiveSuggestions} />
    </div>
  );
}
