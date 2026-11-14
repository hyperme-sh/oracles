# Reachable source history review

At main `58f3a29b8bd67e098f47aa089fe623b80144bd14`, the initial inventory inspected
322 reachable commit/tag/blob objects across HEAD and fetched origin branches
and tags. Historical wheel members were expanded without executing them.
It found 162 hosted-code matches across 12 historical wheel blobs, including old
controlplane API, core, DB and event fixtures. Current neutral runtime checks do
not remove those reachable historical bytes or clear public source distribution.

CI repeats the inventory from a non-shallow checkout and secret-scans historical
objects and expanded wheel members. Logs show exact refs, object/member locations
and counts, never matched secret contents. Hosted history is reported without
blocking ordinary preparation merges; unexpected secret findings fail CI.
No historical objects, refs, tags or releases are rewritten or deleted.

Scope excludes unreachable/deleted refs, hidden server refs, remote Git LFS bytes
and external archives. Matching is not an exhaustive confidentiality review.
Public distribution remains uncleared pending separate historical-content work;
this reporting status adds no human approval gate or GitHub protection setting.

The first secret scan flagged 21 matches: 20 file SHA-256 values and one official
Python signing fingerprint embedded in a scanner configuration. All file hashes
were checked against reachable runtime or archived migration bytes. Exceptions
are limited to those exact object/member IDs and exact hash/fingerprint values;
no source path or credential category is excluded.

[Historical distribution review](historical-distributions/README.md) now records
member-level classifications and the read-only older-image review procedure.
