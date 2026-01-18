import { useEffect } from "react";

import { subscribeToApiEvents } from "../../api";
import { useToast } from "../ui/toast";

export default function ApiEventListener() {
  const toast = useToast();

  useEffect(() => {
    return subscribeToApiEvents((event) => {
      if (event.type === "rate-limit") {
        toast.info(event.message || "You're moving quickly - please slow down and try again.", "Rate limit");
      } else if (event.type === "server-error") {
        toast.error(event.message || "Something went wrong on our side.", "Request failed");
      }
    });
  }, [toast]);

  return null;
}
