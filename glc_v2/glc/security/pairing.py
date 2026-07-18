"""DM pairing flow.

A rotating six-digit code is issued per pairing request and expires after
five minutes. The owner enters the code through the WebUI to confirm.
Per-pairing trust levels live in ~/.glc/pairings.sqlite: owner_paired for
the installation owner, user_paired for explicitly-paired users.

The pairing store is sqlite-backed so it survives restarts.
"""

from dataclasses import dataclass
CODE_TTL_SECONDS = 5 * 60

@dataclass
class PairingRecord:
    channel: str
    channel_user_id: str
    user_handle: str
    trust_level: str
    paired_at: float
