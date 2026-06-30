# Changelog

All notable repository changes are documented here.

## Unreleased

### Added

- Complete Discord application, Windows 10/11 and Ubuntu 24.04 Red installation guide.
- Operations guide for install, update, backup, restore, logs and rollback.
- Full DevelopmentOps guide covering environment, webhook, reverse proxy, Forum sync and troubleshooting.
- Architecture audit for both cogs and a modular vNext proposal.
- Root Red repository metadata, security policy and contributing guide.
- Repository validator, unit tests and GitHub Actions quality workflow.
- Professional badges and project presentation.
- Dependency-free overwrite merge helper and hardened ImperialSetup compatibility layer.
- Safe `.env.example` for DevelopmentOps variable names.

### Changed

- Root README now represents both ImperialSetup and DevelopmentOps.
- Expanded `.gitignore` for Python, IDE, secrets, Red data, backups, logs and media.
- Replaced empty license with MIT License.
- Corrected/expanded cog metadata, ownership and end-user data statements.
- ImperialSetup entrypoint loads the hardened class.
- DevelopmentOps documentation now explicitly describes data copied from Forum to GitHub.

### Fixed

- Preserve custom role/member overwrites when optimizing managed categories/channels.
- Stop mutating when multiple channels match the same canonical name/alias.
- Correct starter embed operation tracking.

### Audited but deferred

- Split the large cog engines into smaller modules.
- Persist DevelopmentOps delivery dedupe/queue.
- Make DevelopmentOps timezone configurable per guild.
- Store ImperialSetup resource IDs and schema versions.
