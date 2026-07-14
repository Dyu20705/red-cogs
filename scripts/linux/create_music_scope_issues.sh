#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${REPO:-${1:-Dyu20705/red-cogs}}"
ASSIGNEE="${ASSIGNEE:-}"
DRY_RUN="${DRY_RUN:-false}"

usage() {
  cat <<'EOF'
Create the music-only migration backlog for Dyu20705/red-cogs.

Usage:
  bash scripts/linux/create_music_scope_issues.sh [OWNER/REPO]

Environment:
  ASSIGNEE=@me   Assign newly created issues (optional)
  DRY_RUN=true   Preview labels and issues without writing to GitHub

Requires: gh, jq
EOF
}

[[ "${1:-}" =~ ^(-h|--help)$ ]] && { usage; exit 0; }
command -v jq >/dev/null || { echo 'error: jq is required' >&2; exit 127; }
if [[ "$DRY_RUN" != true ]]; then
  command -v gh >/dev/null || { echo 'error: gh is required' >&2; exit 127; }
  gh auth status --hostname github.com >/dev/null
  gh repo view "$REPO" --json nameWithOwner >/dev/null
fi

LABELS_JSON='[
  {"name":"type:epic","color":"5319E7","description":"Coordinated multi-issue outcome"},
  {"name":"type:architecture","color":"1D76DB","description":"Architecture and ownership decisions"},
  {"name":"type:refactor","color":"0E8A16","description":"Internal restructuring"},
  {"name":"type:migration","color":"FBCA04","description":"Configuration or deployment migration"},
  {"name":"type:docs","color":"0075CA","description":"Documentation work"},
  {"name":"type:test","color":"BFDADC","description":"Automated or manual verification"},
  {"name":"type:release","color":"D93F0B","description":"Cutover, rollback, and production validation"},
  {"name":"area:music","color":"C5DEF5","description":"Red Audio, Lavalink, queue, playback, and music rooms"},
  {"name":"area:repository","color":"D4C5F9","description":"Repository-wide structure and maintenance"},
  {"name":"priority:p0","color":"B60205","description":"Required before cutover"},
  {"name":"priority:p1","color":"D93F0B","description":"Required for production quality"},
  {"name":"ready-for-agent","color":"EDEDED","description":"Scoped and ready for implementation"}
]'

ISSUES_JSON="$(cat <<'JSON' | jq -c .
[
  {
    "key":"architecture",
    "title":"[ARCHITECTURE] Define the music-only ownership boundary",
    "labels":["type:architecture","area:repository","area:music","priority:p0","ready-for-agent"],
    "body":"## Outcome\n\nDefine `red-cogs` as the Red-DiscordBot music runtime while `Dyu20705/my-discord-bot` owns moderation, study, feeds, GitHub/dev workflow, fun, resources, and general server operations.\n\n## Acceptance criteria\n\n- [ ] Classify every current cog as keep, split, migrate, deprecate, or remove.\n- [ ] Keep Red Audio/Lavalink, playback controls, queue policy, now-playing state, private listening rooms, and music health reporting.\n- [ ] Record command, permission, storage, dependency, and documentation ownership.\n- [ ] Define the compatibility window, target layout, sequencing, and non-goals.\n\n## Definition of done\n\nThe remaining implementation issues can be completed without guessing ownership boundaries."
  },
  {
    "key":"backup",
    "title":"[MIGRATION] Inventory and back up existing Red Config before the split",
    "labels":["type:migration","area:repository","area:music","priority:p0","ready-for-agent"],
    "body":"## Outcome\n\nCreate a secret-safe inventory and recoverable backup before code, config, or cog removal.\n\n## Acceptance criteria\n\n- [ ] Map existing config namespaces and stored IDs to their future owner.\n- [ ] Separate music state from feeds and other state mixed in `imperialautomation`.\n- [ ] Test backup and restore in an isolated Red profile.\n- [ ] Document rollback and block destructive steps without verified backup evidence.\n- [ ] Never commit tokens, Lavalink passwords, private IDs, user exports, or backup archives.\n\n## Definition of done\n\nThe pre-migration state can be restored without exposing deployment secrets."
  },
  {
    "key":"extract",
    "title":"[REFACTOR] Extract music automation from imperialautomation into musicops",
    "labels":["type:refactor","area:music","priority:p0","ready-for-agent"],
    "body":"## Outcome\n\nCreate a standalone `musicops` cog from the music half of `imperialautomation`.\n\n## Acceptance criteria\n\n- [ ] Preserve Red Audio integration, queue quotas, now-playing panels, and private listening rooms.\n- [ ] Remove RSS, digest scheduling, feedparser, and feed configuration from the music runtime.\n- [ ] Cancel tasks cleanly on unload and avoid duplicate listeners, panels, rooms, or jobs after reload.\n- [ ] Keep least-privilege permissions and safe bounded failure handling.\n- [ ] Do not add unrelated music features during extraction.\n\n## Definition of done\n\n`musicops` installs and operates independently of all feed functionality."
  },
  {
    "key":"config-migration",
    "title":"[MIGRATION] Migrate legacy imperialautomation music configuration safely",
    "labels":["type:migration","area:music","priority:p0","ready-for-agent"],
    "body":"## Outcome\n\nProvide an idempotent, rollback-aware migration to a versioned music-only schema.\n\n## Acceptance criteria\n\n- [ ] Fresh installs receive only the new schema.\n- [ ] Existing installs migrate supported music keys exactly once without copying feed state.\n- [ ] Repeated or interrupted migration resumes safely without duplicates or data loss.\n- [ ] Invalid and cross-guild references fail closed with an operator-readable report.\n- [ ] The compatibility and rollback procedure restores the old cog from backup.\n\n## Definition of done\n\nClean and upgraded installations reach a deterministic valid configuration."
  },
  {
    "key":"observability",
    "title":"[MUSIC] Consolidate musicstatus with musicops health and observability",
    "labels":["type:refactor","area:music","priority:p1","ready-for-agent"],
    "body":"## Outcome\n\nMake `musicstatus` the read-only operational view for Red Audio, Lavalink, players, panels, and active music rooms.\n\n## Acceptance criteria\n\n- [ ] Distinguish healthy, degraded, unavailable, and misconfigured states.\n- [ ] Bound health checks with timeouts and avoid blocking command handling.\n- [ ] Degrade safely when Audio or Lavalink is absent.\n- [ ] Redact tokens, passwords, private URLs, IDs where appropriate, and exception internals.\n- [ ] Cover healthy and degraded states with tests.\n\n## Definition of done\n\nOperators have one reliable music-specific troubleshooting surface."
  },
  {
    "key":"retire",
    "title":"[DEPRECATION] Retire non-music cogs after parity verification",
    "labels":["type:refactor","area:repository","priority:p1","ready-for-agent"],
    "body":"## Outcome\n\nDeprecate and remove `imperialsetup`, `developmentops`, `botops`, `studyops`, and the feed half of `imperialautomation` only after ownership is verified.\n\n## Acceptance criteria\n\n- [ ] Every retiring command has a replacement owner, an explicit retirement decision, or a documented temporary gap.\n- [ ] Publish unload, uninstall, data-export, cleanup, and rollback instructions.\n- [ ] Remove stale dependencies, tests, generated command rows, docs, and CI paths with the code.\n- [ ] Do not claim parity where the replacement intentionally differs.\n- [ ] Music cogs remain independently installable throughout the transition.\n\n## Definition of done\n\nNo active non-music runtime responsibility or misleading metadata remains."
  },
  {
    "key":"docs",
    "title":"[DOCS] Rewrite repository metadata and operator docs for music-only scope",
    "labels":["type:docs","area:repository","area:music","priority:p1","ready-for-agent"],
    "body":"## Outcome\n\nRewrite README, cog metadata, command docs, operations, security, migration, and rollback guidance for a focused music repository.\n\n## Acceptance criteria\n\n- [ ] No document advertises retired non-music features.\n- [ ] Install examples load only supported music cogs.\n- [ ] Red Audio and Lavalink prerequisites and least-privilege permissions are explicit.\n- [ ] Upgrade, config migration, backup, restore, and rollback instructions match implementation.\n- [ ] Generated command documentation is refreshed and checked by CI.\n\n## Definition of done\n\nA new operator can install, validate, update, and recover the repository without obsolete instructions."
  },
  {
    "key":"tests",
    "title":"[TEST] Add music-focused CI, migration, and regression coverage",
    "labels":["type:test","area:repository","area:music","priority:p1","ready-for-agent"],
    "body":"## Outcome\n\nCreate a deterministic offline quality gate for the music-only runtime.\n\n## Acceptance criteria\n\n- [ ] Test metadata/imports, fresh config, legacy migration, and rollback fixtures.\n- [ ] Test queue boundaries, task cleanup, cog reload, panel idempotency, and room cleanup.\n- [ ] Test Lavalink unavailable, timeout, restart, and reconnect behavior with fakes.\n- [ ] Fail CI on stale docs, invalid metadata, duplicate tasks, migration regressions, or secret leakage.\n- [ ] Keep real Discord tokens, guilds, and Lavalink nodes out of automated tests.\n\n## Definition of done\n\nCI catches the highest-risk migration and runtime regressions before live validation."
  },
  {
    "key":"release",
    "title":"[RELEASE] Validate the music-only cutover in the designated Discord guild",
    "labels":["type:release","area:repository","area:music","priority:p0","ready-for-agent"],
    "body":"## Outcome\n\nValidate the exact release candidate in the designated guild and intended host with rollback evidence.\n\n## Acceptance criteria\n\n- [ ] Record the exact SHA, Red version, Python version, and host class without secrets.\n- [ ] Verify Audio/Lavalink, playback, queues, now-playing, private rooms, and music status with intended actors.\n- [ ] Reload the cog and restart Red without duplicate tasks, rooms, panels, or corrupted state.\n- [ ] Confirm least-privilege permissions and secret-safe logs.\n- [ ] Demonstrate backup, restore, rollback, and re-upgrade before closing.\n\n## Definition of done\n\nThe cutover is proven operational and recoverable in the real environment."
  }
]
JSON
)"

EPIC_TITLE='[EPIC] Refocus red-cogs as a music-only Red-DiscordBot repository'
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

log() { printf '%s\n' "$*" >&2; }

ensure_labels() {
  jq -c '.[]' <<<"$LABELS_JSON" | while IFS= read -r item; do
    local name color description
    name="$(jq -r '.name' <<<"$item")"
    color="$(jq -r '.color' <<<"$item")"
    description="$(jq -r '.description' <<<"$item")"
    if [[ "$DRY_RUN" == true ]]; then
      log "[dry-run] label: $name"
    else
      gh label create "$name" --repo "$REPO" --color "$color" --description "$description" --force >/dev/null
    fi
  done
}

find_issue_url() {
  gh issue list --repo "$REPO" --state all --limit 1000 --json title,url \
    | jq -r --arg title "$1" '[.[] | select(.title == $title) | .url][0] // empty'
}

create_or_reuse_issue() {
  local title="$1" body="$2" labels_json="$3" url
  if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] issue: $title"
    jq -rn --arg title "$title" '"dry-run://" + ($title | @uri)'
    return
  fi

  url="$(find_issue_url "$title")"
  if [[ -n "$url" ]]; then
    local -a edit_args=(issue edit "$url" --repo "$REPO")
    while IFS= read -r label; do edit_args+=(--add-label "$label"); done < <(jq -r '.[]' <<<"$labels_json")
    gh "${edit_args[@]}" >/dev/null
    log "reuse: $title -> $url"
    printf '%s\n' "$url"
    return
  fi

  local body_file="$TMP_DIR/body.md"
  printf '%s\n' "$body" >"$body_file"
  local -a create_args=(issue create --repo "$REPO" --title "$title" --body-file "$body_file")
  while IFS= read -r label; do create_args+=(--label "$label"); done < <(jq -r '.[]' <<<"$labels_json")
  [[ -n "$ASSIGNEE" ]] && create_args+=(--assignee "$ASSIGNEE")
  url="$(gh "${create_args[@]}")"
  log "created: $title -> $url"
  printf '%s\n' "$url"
}

main() {
  ensure_labels

  local epic_url
  epic_url="$(create_or_reuse_issue "$EPIC_TITLE" 'Child links are populated after issue creation.' '["type:epic","area:repository","area:music","priority:p0"]')"

  : >"$TMP_DIR/results.ndjson"
  jq -c '.[]' <<<"$ISSUES_JSON" | while IFS= read -r issue; do
    local title body labels url
    title="$(jq -r '.title' <<<"$issue")"
    body="$(jq -r '.body' <<<"$issue")"
    labels="$(jq -c '.labels' <<<"$issue")"
    url="$(create_or_reuse_issue "$title" "$body" "$labels")"
    jq -cn --argjson issue "$issue" --arg url "$url" '$issue + {url: $url}' >>"$TMP_DIR/results.ndjson"
  done

  jq -s '.' "$TMP_DIR/results.ndjson" >"$TMP_DIR/results.json"
  local epic_body
  epic_body="$(jq -r '
    "## Outcome\n\nRefocus `red-cogs` into a production-quality, music-only Red-DiscordBot repository. `Dyu20705/my-discord-bot` owns general server workflows; this repository retains Red Audio/Lavalink, queue policy, now-playing state, private listening rooms, and music health.\n\n## Child issues\n\n" +
    (map("- [ ] [" + .title + "](" + .url + ")") | join("\n")) +
    "\n\n## Sequencing\n\n1. Accept ownership boundaries and verify backups.\n2. Extract music runtime and migrate configuration.\n3. Consolidate observability and regression tests.\n4. Retire non-music cogs and rewrite docs.\n5. Validate the exact release candidate and rollback in the real environment.\n\n## Global acceptance criteria\n\n- [ ] Only music-specific runtime responsibilities remain.\n- [ ] Music state migrates safely or has a documented recovery path.\n- [ ] Non-music commands have an explicit replacement or retirement decision.\n- [ ] CI and operator documentation match the final layout.\n- [ ] Live cutover, restart, backup, restore, and rollback evidence pass."
  ' "$TMP_DIR/results.json")"

  if [[ "$DRY_RUN" == true ]]; then
    log '[dry-run] update epic checklist'
  else
    printf '%s\n' "$epic_body" >"$TMP_DIR/epic.md"
    gh issue edit "$epic_url" --repo "$REPO" --body-file "$TMP_DIR/epic.md" >/dev/null
  fi

  jq -n --arg repository "$REPO" --arg epic "$epic_url" \
    --argjson children "$(cat "$TMP_DIR/results.json")" \
    '{repository: $repository, epic: $epic, children: $children}'
}

main
