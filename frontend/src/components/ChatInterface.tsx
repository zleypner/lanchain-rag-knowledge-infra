"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Message, SourceDocument } from "@/types";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { SourceCard } from "./SourceCard";

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentSources, setCurrentSources] = useState<SourceDocument[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading) return;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: input.trim(),
        timestamp: new Date().toISOString(),
        metadata: {},
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setIsLoading(true);
      setStreamingContent("");
      setCurrentSources([]);

      try {
        let fullContent = "";
        let sources: SourceDocument[] = [];
        let newSessionId = sessionId;

        for await (const event of api.chatStream({
          message: userMessage.content,
          session_id: sessionId || undefined,
          include_sources: true,
        })) {
          if (event.event === "token" && typeof event.data === "string") {
            fullContent += event.data;
            setStreamingContent(fullContent);
          } else if (event.event === "sources" && Array.isArray(event.data)) {
            sources = event.data as SourceDocument[];
            setCurrentSources(sources);
          } else if (event.event === "done") {
            // Finalize the message
            const assistantMessage: Message = {
              id: crypto.randomUUID(),
              role: "assistant",
              content: fullContent,
              timestamp: new Date().toISOString(),
              metadata: { sources },
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setStreamingContent("");

            // Update session ID if provided
            if (
              event.data &&
              typeof event.data === "object" &&
              "session_id" in event.data
            ) {
              newSessionId = (event.data as { session_id: string }).session_id;
              setSessionId(newSessionId);
            }
          } else if (event.event === "error") {
            throw new Error(
              typeof event.data === "string" ? event.data : "Stream error"
            );
          }
        }
      } catch (error) {
        const errorMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Error: ${error instanceof Error ? error.message : "Something went wrong"}`,
          timestamp: new Date().toISOString(),
          metadata: {},
        };
        setMessages((prev) => [...prev, errorMessage]);
        setStreamingContent("");
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, sessionId]
  );

  const handleClearChat = () => {
    setMessages([]);
    setSessionId(null);
    setCurrentSources([]);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <h1 className="text-lg font-semibold text-gray-900">Chat</h1>
        {messages.length > 0 && (
          <button
            onClick={handleClearChat}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !streamingContent && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-medium text-gray-900">
              Ask about your documents
            </h2>
            <p className="mt-2 text-gray-500 max-w-md">
              Upload documents and ask questions. The AI will search through
              your knowledge base to provide accurate answers with sources.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex",
              message.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[80%] rounded-lg px-4 py-3",
                message.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-900"
              )}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.role === "assistant" &&
                message.metadata?.sources &&
                (message.metadata.sources as SourceDocument[]).length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs font-medium text-gray-500 mb-2">
                      Sources
                    </p>
                    <div className="space-y-2">
                      {(message.metadata.sources as SourceDocument[]).map(
                        (source, idx) => (
                          <SourceCard key={idx} source={source} />
                        )
                      )}
                    </div>
                  </div>
                )}
            </div>
          </div>
        ))}

        {/* Streaming message */}
        {streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-white border border-gray-200 text-gray-900">
              <p className="whitespace-pre-wrap">{streamingContent}</p>
              <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && !streamingContent && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.1s" }}
                />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-200 bg-white">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your documents..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors",
              input.trim() && !isLoading
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            )}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
