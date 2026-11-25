import { useQuery } from "@tanstack/react-query";
import { get } from "./api";
import { privileged, type DailyResilience, type User } from "./types";

export function useResilience(user: User, day: string) {
  return useQuery({
    queryKey: ["resilience", user.id, day],
    queryFn: () => get<DailyResilience>("/analytics/resilience?day=" + day),
    enabled: privileged(user),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
