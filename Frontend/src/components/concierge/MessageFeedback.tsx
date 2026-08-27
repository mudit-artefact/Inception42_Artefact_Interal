import { Check, Copy, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { MessageAction, MessageActions } from "@/components/ai-elements/message";

interface MessageFeedbackProps {
  content: string;
  feedback?: "up" | "down" | null | undefined;
  onFeedback: (value: "up" | "down") => void;
}

export function MessageFeedback({ content, feedback, onFeedback }: MessageFeedbackProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <MessageActions className="mt-1">
      <MessageAction
        label="Helpful"
        variant="ghost"
        size="icon-sm"
        aria-pressed={feedback === "up"}
        onClick={() => onFeedback("up")}
        className={feedback === "up" ? "text-pink" : "text-muted-foreground"}
      >
        <ThumbsUp className="size-3.5" aria-hidden="true" />
      </MessageAction>
      <MessageAction
        label="Not helpful"
        variant="ghost"
        size="icon-sm"
        aria-pressed={feedback === "down"}
        onClick={() => onFeedback("down")}
        className={feedback === "down" ? "text-destructive" : "text-muted-foreground"}
      >
        <ThumbsDown className="size-3.5" aria-hidden="true" />
      </MessageAction>
      <MessageAction label={copied ? "Copied" : "Copy answer"} variant="ghost" size="icon-sm" onClick={copy}>
        {copied ? (
          <Check className="size-3.5 text-primary" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5 text-muted-foreground" aria-hidden="true" />
        )}
      </MessageAction>
      {feedback ? (
        <span className="ml-1 self-center text-[11px] text-muted-foreground">Thanks — feedback recorded</span>
      ) : null}
    </MessageActions>
  );
}
