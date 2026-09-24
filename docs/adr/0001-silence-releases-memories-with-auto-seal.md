# Silence releases Memories to the Clone, with sensitive categories auto-Sealed

Memories become available to the Clone when their Holding Period ends, using the Visibility the AI proposed, unless the Owner changes it after seeing the Release Digest. We chose opt-out release over explicit review because auto-save only works if the Owner doesn't have to approve every Memory, and a Clone that never gets new Memories goes stale. Because silence counts as consent, sensitive categories (health, money, romance, other people's secrets) are Sealed automatically and never released without the Owner unsealing them. Removing that auto-Seal would mean a missed email could leak a secret to a Visitor.

## Considered Options

- Every Memory needs explicit review before any Visitor sees it: rejected, because the review load kills daily use.
- Release only to Participants: rejected as the only rule, because general Memories (opinions, stories) would never reach anyone.
