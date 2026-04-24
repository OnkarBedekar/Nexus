// urql client wired to Cosmo Router via graphql-sse for subscriptions.
//
// Cosmo Router supports GraphQL subscriptions over SSE by accepting a POST to
// /graphql with `Accept: text/event-stream`. The `graphql-sse` package (by
// enisdenjo, linked from the Cosmo docs) speaks that protocol directly.

import {
  Client,
  cacheExchange,
  fetchExchange,
  subscriptionExchange,
} from "urql";
import { createClient as createSSEClient } from "graphql-sse";

const COSMO_URL = import.meta.env.VITE_COSMO_URL ?? "http://localhost:3002";

const sseClient = createSSEClient({
  url: `${COSMO_URL}/graphql`,
  // Disable single-connection mode to avoid PUT preflights from some clients.
  // Per-operation SSE requests are stable with Cosmo Router CORS defaults.
  singleConnection: false,
  credentials: "omit",
});

export const graphqlClient = new Client({
  url: `${COSMO_URL}/graphql`,
  exchanges: [
    cacheExchange,
    fetchExchange,
    subscriptionExchange({
      forwardSubscription(operation) {
        return {
          subscribe: (sink) => {
            const dispose = sseClient.subscribe(
              {
                query: String(operation.query ?? ""),
                variables: operation.variables as Record<string, unknown>,
                operationName: operation.operationName ?? "",
              },
              sink,
            );
            return { unsubscribe: dispose };
          },
        };
      },
    }),
  ],
});
