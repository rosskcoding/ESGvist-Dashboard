"use client";

import {
  useQuery,
  useMutation,
  type UseQueryOptions,
  type UseMutationOptions,
  type QueryKey,
} from "@tanstack/react-query";
import { api, type AppApiError } from "@/lib/api";

function queryDefaultsForPath(path: string): Pick<
  UseQueryOptions<unknown, AppApiError>,
  | "staleTime"
  | "gcTime"
  | "refetchInterval"
  | "refetchIntervalInBackground"
  | "refetchOnMount"
  | "retry"
> {
  if (path === "/auth/me") {
    return {
      staleTime: 0,
      gcTime: 30 * 60_000,
      refetchOnMount: "always",
      retry: false,
    };
  }

  if (path === "/notifications/unread-count") {
    return {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
      refetchInterval: 30_000,
      refetchIntervalInBackground: true,
    };
  }

  if (/^\/dashboard\/projects\/\d+\/progress$/.test(path)) {
    return {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
    };
  }

  return {};
}

/**
 * Wrapper around useQuery for API GET requests.
 *
 * @param key - React Query cache key
 * @param path - API path (e.g. "/projects")
 * @param options - Additional useQuery options
 */
export function useApiQuery<TData = unknown>(
  key: QueryKey,
  path: string,
  options?: Omit<UseQueryOptions<TData, AppApiError>, "queryKey" | "queryFn">
) {
  const defaults = queryDefaultsForPath(path) as Omit<
    UseQueryOptions<TData, AppApiError>,
    "queryKey" | "queryFn"
  >;
  return useQuery<TData, AppApiError>({
    queryKey: key,
    queryFn: () => api.get<TData>(path),
    ...defaults,
    ...options,
  });
}

/**
 * Wrapper around useMutation for API write requests.
 *
 * @param path - API path (e.g. "/projects")
 * @param method - HTTP method (POST, PUT, PATCH, DELETE)
 * @param options - Additional useMutation options
 */
export function useApiMutation<
  TData = unknown,
  TVariables = unknown,
>(
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE" = "POST",
  options?: Omit<UseMutationOptions<TData, AppApiError, TVariables>, "mutationFn">
) {
  return useMutation<TData, AppApiError, TVariables>({
    mutationFn: async (variables: TVariables) => {
      switch (method) {
        case "POST":
          return api.post<TData>(path, variables);
        case "PUT":
          return api.put<TData>(path, variables);
        case "PATCH":
          return api.patch<TData>(path, variables);
        case "DELETE":
          return api.delete<TData>(path);
      }
    },
    ...options,
  });
}
