"""MacHybridAI Hybrid Compute & PII Guardian Engine."""

__version__ = "1.0.0"

from .guardian import (
    GuardianPolicy,
    PIIEntity,
    PIIGuardian,
    PIIVault,
    RedactionResult,
)
from .m365_proxy import (
    M365CopilotProxyManager,
    M365ModelCatalog,
    M365ToolEmulator,
)
from .orchestrator import (
    ComputeMode,
    ExecutionReceipt,
    HybridConfig,
    HybridOrchestrator,
    StationStep,
    TaskExecutionResult,
)
from .providers import (
    AntigravityProvider,
    GeminiProvider,
    LocalModelProvider,
    M365CopilotProvider,
    OpenAICompatibleProvider,
)

__all__ = [
    "__version__",
    "GuardianPolicy",
    "PIIEntity",
    "PIIGuardian",
    "PIIVault",
    "RedactionResult",
    "M365CopilotProxyManager",
    "M365ModelCatalog",
    "M365ToolEmulator",
    "ComputeMode",
    "ExecutionReceipt",
    "HybridConfig",
    "HybridOrchestrator",
    "StationStep",
    "TaskExecutionResult",
    "AntigravityProvider",
    "GeminiProvider",
    "LocalModelProvider",
    "M365CopilotProvider",
    "OpenAICompatibleProvider",
]
