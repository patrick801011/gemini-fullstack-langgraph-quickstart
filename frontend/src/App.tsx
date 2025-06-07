import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message } from "@langchain/langgraph-sdk";
import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from 'react-i18next'; // Import useTranslation
import { ProcessedEvent } from "@/components/ActivityTimeline";
import { WelcomeScreen } from "@/components/WelcomeScreen";
import { ChatMessagesView } from "@/components/ChatMessagesView";
import LanguageSwitcher from "@/components/LanguageSwitcher"; // Import LanguageSwitcher

export default function App() {
  const { t } = useTranslation(); // Initialize t function
  const [processedEventsTimeline, setProcessedEventsTimeline] = useState<
    ProcessedEvent[]
  >([]);
  const [historicalActivities, setHistoricalActivities] = useState<
    Record<string, ProcessedEvent[]>
  >({});
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const hasFinalizeEventOccurredRef = useRef(false);
  const [isAiResponseComplete, setIsAiResponseComplete] = useState(false);

  const thread = useStream<{
    messages: Message[];
    initial_search_query_count: number;
    max_research_loops: number;
    reasoning_model: string;
  }>({
    apiUrl: import.meta.env.DEV
      ? "http://localhost:2024"
      : "http://localhost:8123",
    assistantId: "agent",
    messagesKey: "messages",
    onFinish: (event: any) => {
      console.log("Stream finished:", event); // Optional: for debugging
      // Only set true if a finalize_answer event actually occurred during this stream.
      if (hasFinalizeEventOccurredRef.current) {
        setIsAiResponseComplete(true);
      }
    },
    onUpdateEvent: (event: any) => {
      let processedEvent: ProcessedEvent | null = null;
      if (event.generate_query) {
        let queryData = "No queries generated"; // Default value
        if (Array.isArray(event.generate_query.query_list) && event.generate_query.query_list.length > 0) {
          queryData = event.generate_query.query_list.join(", ");
        } else if (event.generate_query.query_list) {
          // If it's not an array but some other truthy value, perhaps log or handle specifically
          // For now, we can still say "No queries generated" or try to stringify it if that makes sense.
          // Keeping it simple for this fix:
          console.warn("event.generate_query.query_list was not an array:", event.generate_query.query_list);
        }
        processedEvent = {
          title: "Generating Search Queries",
          data: queryData,

        };
      } else if (event.web_research) {
        const sources = event.web_research.sources_gathered || [];
        const numSources = sources.length;
        let sourcesDetails = "";
        if (numSources > 0) {
          sourcesDetails = sources.slice(0, 3).map((source: any, index: number) => {
            const title = source.title || "No title";
            const snippet = source.snippet || "No snippet";
            // Limit snippet length to avoid overly long lines
            const shortSnippet = snippet.length > 100 ? snippet.substring(0, 97) + "..." : snippet;
            return `Source ${index + 1}: ${title} - ${shortSnippet}`;
          }).join("\n");
        }

        let dataString = t('app.gatheredSources', { numSources });
        if (numSources > 0) {
          dataString += ` ${t('app.topSources', { sourcesDetails })}`;
        } else {
          dataString += ` ${t('app.noSourcesFound')}`;
        }

        processedEvent = {
          title: t('app.webResearch'),
          data: dataString,
        };
      } else if (event.reflection) {
        let reflectionData = "Search successful, generating final answer."; // is_sufficient 為 true 時的預設值
        if (!event.reflection.is_sufficient) {
          const followUpQueries = event.reflection.follow_up_queries;
          if (Array.isArray(followUpQueries) && followUpQueries.length > 0) {
            reflectionData = `Need more information, searching for ${followUpQueries.join(", ")}`;
          } else {
            reflectionData = "Need more information, but no specific follow-up queries provided or list is invalid.";
            console.warn("event.reflection.follow_up_queries was not a non-empty array:", followUpQueries);
          }
        }
        processedEvent = {
          title: "Reflection",
          data: reflectionData,

        };
      } else if (event.finalize_answer) {
        processedEvent = {
          title: t('app.finalizingAnswer'),
          data: t('app.composingFinalAnswer'),
        };
        hasFinalizeEventOccurredRef.current = true;
      }
      if (processedEvent) {
        setProcessedEventsTimeline((prevEvents) => [
          ...prevEvents,
          processedEvent!,
        ]);
      }
    },
  });

  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollViewport = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollViewport) {
        scrollViewport.scrollTop = scrollViewport.scrollHeight;
      }
    }
  }, [thread.messages]);

  useEffect(() => {
    if (isAiResponseComplete && thread.messages.length > 0) {
      const lastMessage = thread.messages[thread.messages.length - 1];
      if (lastMessage && lastMessage.type === "ai" && lastMessage.id) {
        // Capture the timeline as it is when AI response is marked complete.
        setHistoricalActivities((prev) => ({
          ...prev,
          [lastMessage.id!]: [...processedEventsTimeline],
        }));
      }
      // Reset flags for the next interaction cycle
      setIsAiResponseComplete(false);
      hasFinalizeEventOccurredRef.current = false;
    }
  }, [isAiResponseComplete, thread.messages, processedEventsTimeline]); // Dependencies

  const handleSubmit = useCallback(
    (submittedInputValue: string, effort: string, model: string) => {
      if (!submittedInputValue.trim()) return;
      setProcessedEventsTimeline([]);
      hasFinalizeEventOccurredRef.current = false;
      setIsAiResponseComplete(false); // Add this line

      // convert effort to, initial_search_query_count and max_research_loops
      // low means max 1 loop and 1 query
      // medium means max 3 loops and 3 queries
      // high means max 10 loops and 5 queries
      let initial_search_query_count = 0;
      let max_research_loops = 0;
      switch (effort) {
        case "low":
          initial_search_query_count = 1;
          max_research_loops = 1;
          break;
        case "medium":
          initial_search_query_count = 3;
          max_research_loops = 3;
          break;
        case "high":
          initial_search_query_count = 5;
          max_research_loops = 10;
          break;
      }

      const newMessages: Message[] = [
        ...(thread.messages || []),
        {
          type: "human",
          content: submittedInputValue,
          id: Date.now().toString(),
        },
      ];
      thread.submit({
        messages: newMessages,
        initial_search_query_count: initial_search_query_count,
        max_research_loops: max_research_loops,
        reasoning_model: model,
      });
    },
    [thread]
  );

  const handleCancel = useCallback(() => {
    thread.stop();
    window.location.reload();
  }, [thread]);

  return (
    <div className="flex h-screen bg-neutral-800 text-neutral-100 font-sans antialiased">
      <LanguageSwitcher /> {/* Add LanguageSwitcher here */}
      <main className="flex-1 flex flex-col overflow-hidden max-w-4xl mx-auto w-full">
        <div
          className={`flex-1 overflow-y-auto ${
            thread.messages.length === 0 ? "flex" : ""
          }`}
        >
          {thread.messages.length === 0 ? (
            <WelcomeScreen
              handleSubmit={handleSubmit}
              isLoading={thread.isLoading}
              onCancel={handleCancel}
            />
          ) : (
            <ChatMessagesView
              messages={thread.messages}
              isLoading={thread.isLoading}
              scrollAreaRef={scrollAreaRef}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              liveActivityEvents={processedEventsTimeline}
              historicalActivities={historicalActivities}
            />
          )}
        </div>
      </main>
    </div>
  );
}
