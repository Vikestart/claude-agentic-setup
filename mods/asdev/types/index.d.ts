declare module 'claude-code' {
  interface PluginState {
    asdev: { isCollapsed: boolean; nudgedAt: number; lastReply: string; compactingSince: number; cacheAt: number; docsAt: number; contextBase: number; measureBase: boolean; rules: Record<string, { mtimeMs: number; text: string }> }
  }
}

