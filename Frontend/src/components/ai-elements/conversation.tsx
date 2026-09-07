"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UIMessage } from "ai";
import { ArrowDownIcon, DownloadIcon } from "lucide-react";
import type { ComponentProps, HTMLAttributes } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

interface ConversationContextValue {
  isAtBottom: boolean;
  scrollToBottom: (behavior?: ScrollBehavior) => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

const ConversationContext = createContext<ConversationContextValue>({
  isAtBottom: true,
  scrollToBottom: () => {},
  containerRef: { current: null },
});

export const useConversation = () => useContext(ConversationContext);

export type ConversationProps = HTMLAttributes<HTMLDivElement>;

export const Conversation = ({ className, children, ...props }: ConversationProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const isAutoScrollingRef = useRef(false);

  const checkIsAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    const threshold = 100; // pixels from bottom
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    return distance <= threshold;
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const el = containerRef.current;
    if (!el) return;
    isAutoScrollingRef.current = true;
    el.scrollTo({
      top: el.scrollHeight,
      behavior,
    });
    setTimeout(() => {
      isAutoScrollingRef.current = false;
      setIsAtBottom(true);
    }, 200);
  }, []);

  const handleScroll = useCallback(() => {
    if (isAutoScrollingRef.current) return;
    setIsAtBottom(checkIsAtBottom());
  }, [checkIsAtBottom]);

  // Auto-scroll when new content arrives if user is already at the bottom
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new MutationObserver(() => {
      if (checkIsAtBottom()) {
        scrollToBottom("instant");
      }
    });

    observer.observe(el, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => observer.disconnect();
  }, [checkIsAtBottom, scrollToBottom]);

  return (
    <ConversationContext.Provider
      value={{
        isAtBottom,
        scrollToBottom,
        containerRef,
      }}
    >
      <div
        ref={containerRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        className={cn(
          "relative flex-1 min-h-0 overflow-y-auto overflow-x-hidden scroll-smooth",
          className
        )}
        {...props}
      >
        {children}
      </div>
    </ConversationContext.Provider>
  );
};

export type ConversationContentProps = HTMLAttributes<HTMLDivElement>;

export const ConversationContent = ({
  className,
  children,
  ...props
}: ConversationContentProps) => (
  <div className={cn("flex flex-col gap-6 p-4", className)} {...props}>
    {children}
  </div>
);

export type ConversationEmptyStateProps = HTMLAttributes<HTMLDivElement> & {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
};

export const ConversationEmptyState = ({
  className,
  title = "No messages yet",
  description = "Start a conversation to see messages here",
  icon,
  children,
  ...props
}: ConversationEmptyStateProps) => (
  <div
    className={cn(
      "flex size-full flex-col items-center justify-center gap-3 p-8 text-center",
      className
    )}
    {...props}
  >
    {children ?? (
      <>
        {icon && <div className="text-muted-foreground">{icon}</div>}
        <div className="space-y-1">
          <h3 className="font-medium text-sm">{title}</h3>
          {description && (
            <p className="text-muted-foreground text-sm">{description}</p>
          )}
        </div>
      </>
    )}
  </div>
);

export type ConversationScrollButtonProps = ComponentProps<typeof Button>;

export const ConversationScrollButton = ({
  className,
  ...props
}: ConversationScrollButtonProps) => {
  const { isAtBottom, scrollToBottom } = useConversation();

  if (isAtBottom) return null;

  return (
    <Button
      className={cn(
        "absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full shadow-lg dark:bg-background dark:hover:bg-muted border border-border/80 z-20 cursor-pointer animate-in fade-in zoom-in-95 duration-150",
        className
      )}
      onClick={() => scrollToBottom("smooth")}
      size="icon-sm"
      type="button"
      variant="secondary"
      aria-label="Scroll to bottom"
      {...props}
    >
      <ArrowDownIcon className="size-4" />
    </Button>
  );
};

const getMessageText = (message: UIMessage): string =>
  message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("");

export type ConversationDownloadProps = Omit<
  ComponentProps<typeof Button>,
  "onClick"
> & {
  messages: UIMessage[];
  filename?: string;
  formatMessage?: (message: UIMessage, index: number) => string;
};

const defaultFormatMessage = (message: UIMessage): string => {
  const roleLabel =
    message.role.charAt(0).toUpperCase() + message.role.slice(1);
  return `**${roleLabel}:** ${getMessageText(message)}`;
};

export const messagesToMarkdown = (
  messages: UIMessage[],
  formatMessage: (
    message: UIMessage,
    index: number
  ) => string = defaultFormatMessage
): string => messages.map((msg, i) => formatMessage(msg, i)).join("\n\n");

export const ConversationDownload = ({
  messages,
  filename = "conversation.md",
  formatMessage = defaultFormatMessage,
  className,
  children,
  ...props
}: ConversationDownloadProps) => {
  const handleDownload = useCallback(() => {
    const markdown = messagesToMarkdown(messages, formatMessage);
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [messages, filename, formatMessage]);

  return (
    <Button
      className={cn(
        "absolute top-4 right-4 rounded-full dark:bg-background dark:hover:bg-muted",
        className
      )}
      onClick={handleDownload}
      size="icon"
      type="button"
      variant="outline"
      {...props}
    >
      {children ?? <DownloadIcon className="size-4" />}
    </Button>
  );
};
