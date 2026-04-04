"use client";

import { useState } from "react";
import type { SourceDocument } from "@/types";

interface SourceCardProps {
  source: SourceDocument;
}

export function SourceCard({ source }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const similarityPercent = Math.round(source.similarity_score * 100);

  return (
    <div className="bg-gray-50 rounded-md p-2 text-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full text-left"
      >
        <div className="flex items-center justify-between">
          <span className="font-medium text-gray-700 truncate flex-1">
            {source.source}
          </span>
          <span className="ml-2 text-xs text-gray-500">
            {similarityPercent}% match
          </span>
          <svg
            className={`ml-2 w-4 h-4 text-gray-400 transition-transform ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>
      {isExpanded && (
        <div className="mt-2 pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-600 line-clamp-4">
            {source.content_preview}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Chunk {source.chunk_index + 1}
          </p>
        </div>
      )}
    </div>
  );
}
