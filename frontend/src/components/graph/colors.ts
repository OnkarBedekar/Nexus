import type { EntityType } from "../../types/schema";

// Neon palette — each entity type gets a distinct hue in the cyberpunk
// spectrum so the graph reads like a HUD with classified data streams.
export const NODE_COLOR: Record<EntityType, string> = {
  company: "#00ff88", // Acid green
  person: "#ff00ff", // Hot magenta
  concept: "#ffaa00", // Amber
  claim: "#00d4ff", // Electric cyan (primary)
  paper: "#b57bff", // Neon violet
};

export function nodeRadius(claimsCount: number): number {
  return Math.min(28, 10 + claimsCount * 2);
}
