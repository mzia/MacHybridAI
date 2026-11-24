"""MacHybridAI Hybrid Compute & PII Guardian Engine."""

__version__ = "1.2.0"

from .agent import (
    AgentRunResult,
    AgentToolCall,
    AgentTurnRecord,
    CLISessionStore,
    HybridCLIAgent,
    WorkspaceToolbox,
    diagnose_cli_permissions,
)
from .guardian import (
    GuardianPolicy,
    PIIEntity,
    PIIGuardian,
    PIIVault,
    RedactionResult,
)
from .local_rag import LocalWorkspaceRAG, RAGChunk
from .m365_proxy import (
    M365CopilotProxyManager,
    M365ModelCatalog,
    M365ToolEmulator,
)
from .model_security import (
    FIRST_PARTY_MODEL_ORGS,
    HUGGINGFACE_OVERRIDE_WARNING,
    ModelAuditResult,
    ModelSecuritySettings,
    ModelTrustPolicy,
    audit_model_directory,
    pin_model_to_lockfile,
    sanitize_local_model_dir,
)
from .orchestrator import (
    ComputeMode,
    ExecutionReceipt,
    HybridConfig,
    HybridOrchestrator,
    StationStep,
    TaskExecutionResult,
)
from .profiler import (
    CachedModelStatus,
    HardwareProfiler,
    MacHardwareProfile,
    ModelRecommendation,
)
from .providers import (
    CLOUD_PROVIDER_PRESETS,
    AnthropicProvider,
    AntigravityProvider,
    AppleFoundationModelsProvider,
    GeminiProvider,
    LocalModelProvider,
    M365CopilotProvider,
    OpenAICompatibleProvider,
)

__all__ = [
    "__version__",
    "AgentRunResult",
    "AgentToolCall",
    "AgentTurnRecord",
    "CLISessionStore",
    "HybridCLIAgent",
    "WorkspaceToolbox",
    "diagnose_cli_permissions",
    "GuardianPolicy",
    "PIIEntity",
    "PIIGuardian",
    "PIIVault",
    "RedactionResult",
    "LocalWorkspaceRAG",
    "RAGChunk",
    "M365CopilotProxyManager",
    "M365ModelCatalog",
    "M365ToolEmulator",
    "FIRST_PARTY_MODEL_ORGS",
    "HUGGINGFACE_OVERRIDE_WARNING",
    "ModelAuditResult",
    "ModelSecuritySettings",
    "ModelTrustPolicy",
    "audit_model_directory",
    "pin_model_to_lockfile",
    "sanitize_local_model_dir",
    "ComputeMode",
    "ExecutionReceipt",
    "HybridConfig",
    "HybridOrchestrator",
    "StationStep",
    "TaskExecutionResult",
    "CachedModelStatus",
    "HardwareProfiler",
    "MacHardwareProfile",
    "ModelRecommendation",
    "CLOUD_PROVIDER_PRESETS",
    "AnthropicProvider",
    "AntigravityProvider",
    "AppleFoundationModelsProvider",
    "GeminiProvider",
    "LocalModelProvider",
    "M365CopilotProvider",
    "OpenAICompatibleProvider",
]
