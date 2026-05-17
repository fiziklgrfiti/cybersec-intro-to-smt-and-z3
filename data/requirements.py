"""
NIST CSF 2.0 — PR.AA (Identity Management, Authentication, and Access Control)
Source: https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf
"""

NIST_PR_AA = {
    "framework": "NIST CSF 2.0",
    "domain": "PROTECT (PR)",
    "category_id": "PR.AA",
    "category_name": "Identity Management, Authentication, and Access Control",
    "category_description": (
        "Access to physical and logical assets is limited to authorized users, services, "
        "and hardware and managed commensurate with the assessed risk of unauthorized access"
    ),
    "requirements": [
        {
            "id": "PR.AA-01",
            "text": (
                "Identities and credentials for authorized users, services, and hardware "
                "are managed by the organization"
            ),
        },
        {
            "id": "PR.AA-02",
            "text": (
                "Identities are proofed and bound to credentials based on the context "
                "of interactions"
            ),
        },
        {
            "id": "PR.AA-03",
            "text": "Users, services, and hardware are authenticated",
        },
        {
            "id": "PR.AA-04",
            "text": "Identity assertions are protected, conveyed, and verified",
        },
        {
            "id": "PR.AA-05",
            "text": (
                "Access permissions, entitlements, and authorizations are defined in a policy, "
                "managed, enforced, and reviewed, and incorporate the principles of least "
                "privilege and separation of duties"
            ),
        },
        {
            "id": "PR.AA-06",
            "text": (
                "Physical access to assets is managed, monitored, and enforced "
                "commensurate with risk"
            ),
        },
    ],
}
