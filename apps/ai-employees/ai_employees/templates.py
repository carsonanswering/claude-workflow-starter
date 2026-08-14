"""Built-in `hire` templates, per docs/hiring-ux.md.

A template is an Employee YAML fragment (role, job_description, tools,
approval_gates) missing id/name/status, plus a `description` field shown to
the owner before hire. No new dataclass, no new storage — hiring just
instantiates one of these and appends it to the company YAML's `employees`
list.

`job_description` may contain a `{company}` placeholder, filled in with the
target company's name at hire time.
"""

TEMPLATES: dict[str, dict] = {
    "engineer": {
        "description": "Builds and ships the company's product surface.",
        "role": "engineer",
        "job_description": (
            "Build and ship {company}'s web presence. Scope: this repo only. "
            "Quality bar: tests pass, page renders. Escalate anything "
            "touching prod or data."
        ),
        "tools": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
        "approval_gates": ["deploy_prod", "delete_data"],
    },
    "marketer": {
        "description": "Writes copy and outreach; nothing external without sign-off.",
        "role": "marketer",
        "job_description": (
            "Write {company}'s copy and outreach. Draft freely; NOTHING "
            "leaves the building without owner sign-off. Escalate pricing "
            "or claims you can't source."
        ),
        "tools": ["Read", "Write", "WebSearch", "WebFetch"],
        "approval_gates": ["send_external", "spend_money"],
    },
    "support": {
        "description": "Handles customer questions and refunds within policy.",
        "role": "support",
        "job_description": (
            "Handle {company}'s customer support: answer questions, "
            "troubleshoot, and process refunds within policy. Escalate "
            "anything outside policy or of unclear entitlement."
        ),
        "tools": ["Read", "WebSearch"],
        "approval_gates": ["send_external", "refund_money"],
    },
    "ops": {
        "description": "Runs infrastructure, deploys, and data operations.",
        "role": "ops",
        "job_description": (
            "Keep {company}'s infrastructure running: deploys, environment "
            "config, and data operations. Escalate irreversible or "
            "production-impacting changes."
        ),
        "tools": ["Read", "Write", "Bash"],
        "approval_gates": ["spend_money", "delete_data", "deploy_prod"],
    },
    "researcher": {
        "description": "Reads, searches, and synthesizes findings. No side effects.",
        "role": "researcher",
        "job_description": (
            "Research and synthesize for {company}: read sources, search "
            "the web, and produce findings. Pure read/synthesize — no "
            "side-effecting tools in the allowlist."
        ),
        "tools": ["Read", "WebSearch", "WebFetch"],
        "approval_gates": [],
    },
}
