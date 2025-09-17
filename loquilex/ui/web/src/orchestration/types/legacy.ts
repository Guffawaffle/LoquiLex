/**
 * Legacy Types - Re-exports for backwards compatibility
 * 
 * This re-exports existing types from the main types module to maintain
 * backwards compatibility while transitioning to the orchestration layer.
 */

// Re-export existing types from the main types module
export type { 
  AsrModel, 
  MtModel, 
  SelfTestResp, 
  SessionCfg, 
  EventMsg, 
  DownloadMsg 
} from '../../types'