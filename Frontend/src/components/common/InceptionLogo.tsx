import React from "react";

interface InceptionLogoProps {
  className?: string;
  height?: number | string;
}

export function InceptionLogo({ className = "h-7 w-auto", height }: InceptionLogoProps) {
  return (
    <svg
      viewBox="0 0 178 44"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={height ? { height } : undefined}
      className={`inline-block select-none shrink-0 text-foreground ${className}`}
      aria-label="Inception 42"
    >
      {/* Neon Lime Green Square Dot positioned at the top-left of the 'i' */}
      <rect x="0.5" y="6" width="7" height="7" fill="#84EE00" rx="0.5" />
      {/* Stem of the 'i' */}
      <rect x="7.5" y="16" width="7" height="23" fill="currentColor" rx="0.5" />
      {/* Word 'nception' using modern geometric typography */}
      <text
        x="17"
        y="39"
        fill="currentColor"
        fontFamily="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
        fontSize="31"
        fontWeight="700"
        letterSpacing="-0.035em"
      >
        nception
      </text>
      {/* Superscript '42' */}
      <text
        x="142"
        y="21"
        fill="currentColor"
        fontFamily="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
        fontSize="17"
        fontWeight="700"
        letterSpacing="-0.02em"
      >
        42
      </text>
    </svg>
  );
}
