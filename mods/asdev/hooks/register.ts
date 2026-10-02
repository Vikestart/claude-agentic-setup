import type { Register } from 'claude-code'
import { register as band } from './band'
import { register as compaction } from './compaction'

// The engine takes one hooks module per plugin; each concern keeps its own file (the guards run
// from compaction.ts's tool.call hook).
export const register: Register = (on, options) => {
  band(on, options)
  compaction(on, options)
}
