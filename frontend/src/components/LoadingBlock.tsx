import React from "react";

type LoadingBlockProps = {
  lines?: number;
  className?: string;
  height?: number;
};

export default function LoadingBlock({ lines = 3, className = "", height = 14 }: LoadingBlockProps) {
  return (
    <div className={className}>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={`loading-line-${index}`}
          className="skeleton"
          style={{
            height,
            width: index === lines - 1 ? "64%" : "100%",
          }}
        />
      ))}
    </div>
  );
}

