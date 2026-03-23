"use client";

import {
  useQuery,
  useMutation,
  type UseQueryOptions,
  type UseMutationOptions,
  type QueryKey,
} from "@tanstack/react-query";
import { api } from "@/lib/api";

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
  options?: Omit<UseQueryOptions<TData, Error>, "queryKey" | "queryFn">
) {
  return useQuery<TData, Error>({
    queryKey: key,
    queryFn: () => api.get<TData>(path),
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
  options?: Omit<UseMutationOptions<TData, Error, TVariables>, "mutationFn">
) {
  return useMutation<TData, Error, TVariables>({
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
