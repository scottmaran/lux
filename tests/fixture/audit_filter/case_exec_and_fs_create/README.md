# case_exec_and_fs_create

Invariant: an owned exec followed by a filesystem create emits deterministic
`exec` and `fs_create` rows and preserves `job_id` attribution.
