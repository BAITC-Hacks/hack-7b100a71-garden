import { QueryClient } from '@tanstack/react-query'

export const queryKeys = {
  employees: ['employees'] as const,
  employee: (id: string) => ['employee', id] as const,
  history: (id: string) => ['history', id] as const,
  completion: (id: string) => ['activity-completion', id] as const,
  recommendations: (id: string) => ['recommendations', id] as const,
  hr: ['hr-analytics'] as const,
  events: ['events'] as const,
  datasetUpload: ['dataset-upload'] as const,
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: false, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
})
