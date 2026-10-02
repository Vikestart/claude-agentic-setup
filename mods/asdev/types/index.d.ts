declare module 'claude-code' {
  interface PluginState {
    asdev: { isCollapsed: boolean; nudgedAt: number; lastReply: string; compactingSince: number }
  }
}

