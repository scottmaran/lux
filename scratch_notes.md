# To Dos:
- filter audit logs
- decide if we want host access to agent container on port 22

### Higher-level explanation of each
We are building a containerized harness that watches what an AI agent does at the OS level. The harness runs the agent, captures its
stdout/stderr, and a privileged collector watches the VM kernel for: process starts, file changes, and (via eBPF) network and IPC
connections. Those logs are stored outside the agent’s reach and stitched into a timeline.

To get a verifiable within an explicit scope of how the agent is acting, we need:
- OS auditing telling you what proceses start, with what args, and filesystem metadata events.
- File‑write logs show local filesystem changes; (not reads because of verbosity)
- Network logs capture remote side effects (HTTP, APIs, etc.) even when no files change.
- IPC/service logs capture local daemon interactions (keychain, DBs, launchd) that don’t require exec or file writes.
- Stdout/stderr capture is the only way to record results when the agent just prints to the console.

Implementation at a high level:
- Kernel‑level audit for exec + file writes/renames/unlinks + filesystem metadata events
- Network capture via OS socket/audit hooks or a forced proxy (HTTP) plus firewall logs for raw TCP/UDP.
- IPC/service visibility via OS audit for local socket connections and/or service‑specific logs.
- Stdout/stderr captured by the supervisor process (pipes for non‑interactive, PTY for interactive).

Maybe to do in future: environment variables, metadata like permissions (e.g. chmod)
- Capture environment snapshots at session start and before each exec/tool call.

### Correlating events

By “correlate events by PID/PPID and session ID; map to agent‑visible actions,” I mean:

  - You’ll have multiple event streams (exec, file changes, network connects, IPC connects, stdout/stderr).
  - The PID/PPID tree is the glue: exec events give you PID, PPID, command, time. If a file/IPC/network event includes
    PID, you can join it to the process that caused it.
  - The session ID tags the root agent process; every descendant process inherits that session tag by PPID lineage.

  So you end up with a single timeline like:

  1. Exec: /bin/sh -c "rg foo" (PID 1234, PPID agent)
  2. File write: ~/.cache/rg (PID 1234)
  3. Network connect: api.example.com:443 (PID 1234)
  4. Stdout: “results…” (PID 1234)

  That’s the correlation: “these file/network events happened inside that process which was started by the agent in
  this session.”

  A few important caveats:

  - You only get strong correlation if your audit source includes PID on file/network/IPC events.
      - If you only have FSEvents-style file change logs (no PID), you can only “guess” by time window, which is much
        weaker.
  - One process can run multiple logical actions.
    If the agent runs bash -c "cmd1; cmd2", it’s one PID. You can’t separate cmd1 vs cmd2 without shell
    instrumentation. So the “agent‑visible action” is often the process itself (the command line).
  - “Agent‑visible actions” can be either:
      - Process‑level actions (exec entries), or
      - Tool‑call‑level actions if your wrapper logs tool calls.
        If you don’t instrument tools, your best unit is the process start.

  So yes: the process tree alone doesn’t show file changes, but file events that include PID let you attribute them to
  a process. That’s what the correlation step is doing.

- Event streams are not strictly sequential. They’re time‑ordered, but multiple processes can run
in parallel, and a single process can emit interleaved file/network/IPC events. You’ll build a
timeline by timestamp + PID, not by assuming a single sequence.
- “Session ID tags the root agent process” means: when the wrapper launches the agent, it assigns
a session ID to that root PID in your log. Every descendant process (child of the agent or
further down the PPID chain) inherits that same session ID by lineage. So in the earlier
example, the “PPID agent” was shorthand for “the parent is the agent’s root process, which has
session_id=X, so this child is also session_id=X.”
- Stdout can help but it’s not reliable for correlation. Some agents print the commands they run
(helpful), others don’t, and outputs can be truncated or suppressed. Stdout tells you “what the
agent reported,” not “what actually executed.” The most robust mapping is still PID‑based audit
data. If you log stdout, treat it as supplementary evidence, not the primary source of truth.

### Interactive Sessions 

You can run the agent in a container and still use it interactively as a TUI, as long as the harness provides a real TTY and acts as the I/O proxy.

How it works in practice:

- Allocate a PTY in the harness and run the container process with the PTY slave as its stdin/
  stdout/stderr. The harness reads/writes the PTY master and forwards data to/from the user’s
  terminal.
- Put the user’s terminal in raw mode while the session is active and restore it on exit.
- Forward signals and window size changes (SIGWINCH, SIGINT, SIGTERM) so the TUI behaves
  correctly.
- Log both directions: stdin (user input) and the PTY output stream. In TTY mode stdout/stderr are
  merged, so you’ll log a single output stream (with timestamps) rather than separate channels.

If you don’t do this and instead use pipes, most TUIs won’t render or accept interactive input
properly. The PTY proxy is the key.

Implementation note: the exact attach API depends on the runtime. For Docker/containerd/runc, you
need to create the container with a TTY and attach through your harness (not directly from the
user terminal) so you can proxy and log the stream.

If you want, tell me which container runtime you’re targeting (Docker, containerd, podman, etc.)
and I can outline the exact attach/PTY flow.

### Random blocks of text

I don't want to block execve access and limit a third party agent to only using a personally crafted MCP to run execution through because then I may as well just make my own agent. Instead, I want to allow it to use its tools but log when it does so.

Execve logging ≠ change logging: exec events tell you a process started, not whether anything changed; you still need file‑write/open/rename/delete events to know actual disk changes.

The only reliable path is out‑of‑process observation. You can’t get true “tool‑call logs” without instrumenting the agent, but you can get “side‑effect logs” by watching the agent process and the workspace.

System settings worth logging are mostly file‑backed, but often not in dotfiles:
- User prefs: ~/Library/Preferences/*.plist
- Startup items: ~/Library/LaunchAgents, /Library/LaunchDaemons
- Shell/config: ~/.zshrc, ~/.bashrc, ~/.config/*
- System config: /etc/*, ~/.ssh/config, ~/.gitconfig

Potential gaps to consider:
- Inputs that influence output but don’t change state: file reads, network responses, environment variables, config
files, model/version, time/locale. If you want reproducibility, log read targets or hashes and capture key env/
config at session start.
- Metadata changes: chmod/chown/utime, symlink creation, xattrs, mount/unmount. These are state changes even if
content doesn’t change.
- Privilege and identity changes: sudo, setuid, container escapes, user switching; these matter for attribution.
- Long‑lived daemons/side effects: if the agent triggers a service that keeps running after the session, you’ll miss
later effects unless you track process lineage and lifetimes.
- Log integrity: if logs are stored locally, the agent could tamper. Hash‑chain/sign logs or write to an append‑only
sink.
- Privacy/redaction: full stdout/stderr and network payloads may include secrets. Decide what to redact or hash.

- Environment variables: env changes are per‑process and happen in memory (setenv), not via exec. There’s no kernel
    event for “env changed.” So you won’t see it in OS audit. The practical way is to snapshot env at process start
    (when you spawn the agent or each tool) and log it as part of the session metadata. If a tool runs a shell command
    like FOO=bar cmd, that env is just an argument; log the command line and you’ve captured it.

Short answer: metadata changes are only captured if your OS audit is configured to watch those specific syscalls/
  events. Exec logging alone won’t show them.

  - If your auditing is exec‑only, chmod/chown/xattr/utime will be missed.
  - If your auditing includes filesystem metadata events, then yes, those syscalls are captured.

  So it depends on what you instrument:

  - Syscall/audit‑level hooks (auditd/eBPF/Endpoint Security) can log chmod, chown, setxattr, utimes, etc. if you
    enable those event types.
  - Filesystem change notifiers (FSEvents/inotify) may emit attribute‑change events, but they can be coarse or
    aggregated and aren’t as reliable for audit.

  If you want metadata changes in scope, make it explicit: “log file metadata syscalls,” not just create/write/rename/
  unlink.

#### Cgroups

A cgroup namespace is a Linux namespace that virtualizes the cgroup hierarchy a process sees.

Quick mental model:

- cgroups are the kernel’s “resource groups” (CPU/memory/IO/pids). They’re exposed under /sys/fs/cgroup, and
  membership is listed in /proc/<pid>/cgroup.
- cgroup namespace makes a process see a subtree as if it were the root of /sys/fs/cgroup, hiding the rest. Think
  “chroot, but for cgroups.”

Why it matters here:

- The collector uses cgroup IDs from the kernel (eBPF) to attribute events to containers.
- If the collector runs in a separate cgroup namespace, it only sees its own subtree, so the paths in /proc/
  <pid>/cgroup and /sys/fs/cgroup can be relative or incomplete compared to the host’s view.
- With cgroupns: host, the collector sees the same cgroup hierarchy as the host/VM, so cgroup IDs and paths line
  up and can be mapped reliably to containers.

So cgroupns: host is about consistent visibility and mapping, not extra privileges by itself.


### Definitions

IPC (inter‑process communication) is how one running process talks to another without spawning it: local sockets,
named pipes, shared memory, Mach ports/XPC on macOS, D‑Bus on Linux. This is different from exec: no new process is
created. Example: a keychain lookup calls Security.framework, which talks to securityd over XPC; no exec, and no
obvious file change.

## Trust Model 

- Trusted: the host/log sink outside the VM, plus the collector (privileged) that writes logs there.
- Untrusted: the agent container (it can become root, so it must not be able to tamper with logs).
- Harness: typically treated as trusted control‑plane (because it orchestrates tests and reads logs), but it should still be minimally
  privileged and should not be able to rewrite logs.
  