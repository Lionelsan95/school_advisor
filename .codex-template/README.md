# Codex project configuration template

This directory mirrors the project-scoped `.codex/` configuration expected by
Codex. The current execution environment mounts `.codex/` read-only, so these
files are staged here rather than activated in place.

Outside that protected session, copy `config.toml` and `agents/` into the
repository's `.codex/` directory, preserving their relative paths. Then start a
new Codex session so project instructions and custom agents are rediscovered.

`AGENTS.md` is already active as the repository-level instruction entry point.
The custom agents below are Codex-native translations of the roles under
`.claude/agents/`, plus the missing project-specific `neutrality_checker`.
