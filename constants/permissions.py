"""Operational RBAC permission constants (Phase E3)."""

from constants.operators import OPERATOR_ROLES

# Permission identifiers
PERM_VIEW_OPERATIONS = "view_operations"
PERM_VIEW_ANALYTICS = "view_analytics"
PERM_EXPORT = "export"
PERM_MUTATE_WORKFLOW = "mutate_workflow"
PERM_MUTATE_APPLICATION_PROFILE = "mutate_application_profile"
PERM_MUTATE_UNDERWRITING = "mutate_underwriting"
PERM_MUTATE_LOAN_ACCOUNT = "mutate_loan_account"
PERM_MUTATE_REPAYMENTS = "mutate_repayments"
PERM_MANAGE_OPERATORS = "manage_operators"
PERM_VIEW_COLLECTIONS = "view_collections"
PERM_MUTATE_COLLECTIONS = "mutate_collections"

_ALL_PERMISSIONS = frozenset(
    {
        PERM_VIEW_OPERATIONS,
        PERM_VIEW_ANALYTICS,
        PERM_EXPORT,
        PERM_MUTATE_WORKFLOW,
        PERM_MUTATE_APPLICATION_PROFILE,
        PERM_MUTATE_UNDERWRITING,
        PERM_MUTATE_LOAN_ACCOUNT,
        PERM_MUTATE_REPAYMENTS,
        PERM_MANAGE_OPERATORS,
        PERM_VIEW_COLLECTIONS,
        PERM_MUTATE_COLLECTIONS,
    }
)

_OPS_COLLECTIONS = frozenset({PERM_VIEW_COLLECTIONS, PERM_MUTATE_COLLECTIONS})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "administrator": _ALL_PERMISSIONS,
    "operations_manager": (_ALL_PERMISSIONS - {PERM_MANAGE_OPERATORS}) | _OPS_COLLECTIONS,
    "review_officer": frozenset(
        {
            PERM_VIEW_OPERATIONS,
            PERM_VIEW_ANALYTICS,
            PERM_MUTATE_WORKFLOW,
            PERM_MUTATE_APPLICATION_PROFILE,
            PERM_MUTATE_UNDERWRITING,
        }
    ),
    "analyst": frozenset(
        {
            PERM_VIEW_OPERATIONS,
            PERM_VIEW_ANALYTICS,
            PERM_EXPORT,
            PERM_VIEW_COLLECTIONS,
        }
    ),
}

PERMISSION_DENIED_MESSAGES: dict[str, str] = {
    PERM_VIEW_OPERATIONS: "You do not have permission to access operational workspaces.",
    PERM_VIEW_ANALYTICS: "You do not have permission to access analytics or reports.",
    PERM_EXPORT: "You do not have permission to export operational data.",
    PERM_MUTATE_WORKFLOW: "Your role cannot update application workflow status.",
    PERM_MUTATE_APPLICATION_PROFILE: "Your role cannot update applicant profile details.",
    PERM_MUTATE_UNDERWRITING: "Your role cannot record underwriting or financing decisions.",
    PERM_MUTATE_LOAN_ACCOUNT: "Your role cannot update loan account or lifecycle details.",
    PERM_MUTATE_REPAYMENTS: "Your role cannot record or modify repayments.",
    PERM_MANAGE_OPERATORS: "Only administrators can manage operator accounts.",
    PERM_VIEW_COLLECTIONS: "You do not have permission to access the collections workspace.",
    PERM_MUTATE_COLLECTIONS: "Your role cannot update collections or recovery records.",
}


def permissions_for_role(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def is_known_role(role: str) -> bool:
    return role in OPERATOR_ROLES
