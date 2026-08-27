import React from "react";
import logoImg from "@/assets/inception-logo.png";

interface InceptionLogoProps {
  className?: string;
  height?: number | string;
}

export function InceptionLogo({ className = "h-7 w-auto", height }: InceptionLogoProps) {
  return (
    <img
      src={logoImg}
      alt="Inception 42"
      style={height ? { height } : undefined}
      className={`object-contain dark:brightness-0 dark:invert ${className}`}
    />
  );
}

