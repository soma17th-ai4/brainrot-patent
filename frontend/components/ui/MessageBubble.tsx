import { cn } from "@/lib/utils";

interface Props {
  role: "user" | "bot";
  children: React.ReactNode;
}

export function MessageBubble({ role, children }: Props) {
  const isUser = role == "user";
  return (
    <div
      className={cn(
        "lex w-full mb-3",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm break-words",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-card border border-border rounded-bl-sm",
        )}
      >
        {children}
      </div>
    </div>
  );
}
