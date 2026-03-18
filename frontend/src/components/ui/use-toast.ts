type ToastVariant = "default" | "destructive";

interface ToastOptions {
  title?: string;
  description?: string;
  variant?: ToastVariant;
}

/**
 * Minimal toast hook fallback.
 * Keeps call sites working even when a full toast system is not wired yet.
 */
export function useToast() {
  const toast = ({ title, description, variant = "default" }: ToastOptions) => {
    const prefix = variant === "destructive" ? "[Error]" : "[Info]";
    const message = [title, description].filter(Boolean).join(" - ");

    if (variant === "destructive") {
      console.error(prefix, message);
      return;
    }

    console.log(prefix, message);
  };

  return { toast };
}

