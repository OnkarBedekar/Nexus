// GraphQL subscription documents that hit the Cosmo Router. Kept as plain
// strings (not `gql`) so we don't drag in extra tooling; urql's fetchExchange
// is happy with strings.

export const NODE_ADDED = /* GraphQL */ `
  subscription NodeAdded($sessionId: ID!) {
    nodeAdded(sessionId: $sessionId) {
      id
    }
  }
`;

export const EDGE_LINKED = /* GraphQL */ `
  subscription EdgeLinked($sessionId: ID!) {
    edgeLinked(sessionId: $sessionId) {
      id
    }
  }
`;

export const AGENT_STATUS_CHANGED = /* GraphQL */ `
  subscription AgentStatusChanged($sessionId: ID!) {
    agentStatusChanged(sessionId: $sessionId) {
      id
    }
  }
`;

export const CRAWL_LOG = /* GraphQL */ `
  subscription CrawlLog($sessionId: ID!) {
    crawlLog(sessionId: $sessionId) {
      id
    }
  }
`;

export const COLLABORATOR_EVENT = /* GraphQL */ `
  subscription CollaboratorEvent($sessionId: ID!) {
    collaboratorEvent(sessionId: $sessionId) {
      id
    }
  }
`;
