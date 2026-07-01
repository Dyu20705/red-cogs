# Command Reference

Generated from source by `python scripts/generate_command_reference.py`.
Do not edit command rows by hand.

| Cog | Command | Type | Function | Aliases | Checks | Source | Description |
|---|---|---|---|---|---|---|---|
| botops | `[p]botops` | group | `botops` | - | guild only, admin/manage guild | `botops/botops.py:120` | Configure operational audit and incident logging. |
| botops | `[p]botops cleanupnow` | command | `cleanup_now` | - | - | `botops/botops.py:255` | Run log retention cleanup immediately. |
| botops | `[p]botops health` | command | `health` | `doctor` | - | `botops/botops.py:245` | Show a deep, redacted bot health diagnostic. |
| botops | `[p]botops retention` | command | `set_retention` | - | - | `botops/botops.py:170` | Set #bot-logs retention between 7 and 30 days. |
| botops | `[p]botops set` | command | `set_channel` | - | - | `botops/botops.py:127` | Set a channel: audit, errors, or logs. |
| botops | `[p]botops status` | command | `configuration_status` | - | - | `botops/botops.py:191` | Show current BotOps configuration. |
| botops | `[p]botops test` | command | `test_pipeline` | - | - | `botops/botops.py:211` | Test audit/error/log delivery. |
| developmentops | `[p]devset` | group | `devset` | - | guild only, admin/manage guild | `developmentops/developmentops.py:160` | Configure DevelopmentOps. |
| developmentops | `[p]devset channel` | command | `devset_channel` | - | - | `developmentops/developmentops.py:266` | Set `feed`, `release`, `review`, or `daily` channel. |
| developmentops | `[p]devset forum` | command | `devset_forum` | - | - | `developmentops/developmentops.py:312` | Set the bugs-and-ideas Forum channel. |
| developmentops | `[p]devset forumsync` | command | `devset_forum_sync` | - | - | `developmentops/developmentops.py:344` | Enable or disable Discord Forum → GitHub Issue sync. |
| developmentops | `[p]devset milestone` | command | `devset_milestone` | - | - | `developmentops/developmentops.py:365` | Set the milestone used in morning development goals. |
| developmentops | `[p]devset postgoals` | command | `devset_post_goals` | - | - | `developmentops/developmentops.py:515` | Post DEVELOPMENT GOALS immediately. |
| developmentops | `[p]devset refreshpr` | command | `devset_refresh_pr` | - | - | `developmentops/developmentops.py:522` | Create or refresh a PR review thread. |
| developmentops | `[p]devset repo` | group | `devset_repo` | - | - | `developmentops/developmentops.py:167` | Manage watched GitHub repositories. |
| developmentops | `[p]devset repo add` | command | `devset_repo_add` | - | - | `developmentops/developmentops.py:174` | Add `owner/repository` to this Discord server. |
| developmentops | `[p]devset repo primary` | command | `devset_repo_primary` | - | - | `developmentops/developmentops.py:234` | Set the repository used for Forum sync and daily goals. |
| developmentops | `[p]devset repo remove` | command | `devset_repo_remove` | - | - | `developmentops/developmentops.py:204` | Remove a watched repository. |
| developmentops | `[p]devset reviewlabel` | command | `devset_review_label` | - | - | `developmentops/developmentops.py:399` | Set the label that creates a code-review thread. |
| developmentops | `[p]devset schedule` | command | `devset_schedule` | - | - | `developmentops/developmentops.py:424` | Set the morning DEVELOPMENT GOALS time in the configured timezone. |
| developmentops | `[p]devset status` | command | `devset_status` | - | - | `developmentops/developmentops.py:474` | Show configuration without revealing any secret. |
| developmentops | `[p]devset timezone` | command | `devset_timezone` | - | - | `developmentops/developmentops.py:453` | Set the DEVELOPMENT GOALS timezone, e.g. Asia/Bangkok. |
| imperialautomation | `[p]ia` | group | `ia` | `imperialautomation` | guild only | `imperialautomation/imperialautomation.py:91` | ImperialAutomation controls. |
| imperialautomation | `[p]ia feed` | group | `ia_feed` | - | admin/manage guild | `imperialautomation/imperialautomation.py:195` | Manage filtered RSS/Atom feeds. |
| imperialautomation | `[p]ia feed add` | command | `feed_add` | - | - | `imperialautomation/imperialautomation.py:202` | Add a feed: `!ia feed add dev URL Source name`. |
| imperialautomation | `[p]ia feed checknow` | command | `feed_check_now` | - | - | `imperialautomation/imperialautomation.py:471` | Run one feed cycle now. |
| imperialautomation | `[p]ia feed digestnow` | command | `feed_digest_now` | - | - | `imperialautomation/imperialautomation.py:478` | Post today's digest immediately. |
| imperialautomation | `[p]ia feed digesttime` | command | `feed_digest_time` | - | - | `imperialautomation/imperialautomation.py:444` | Set daily digest time in UTC+7. |
| imperialautomation | `[p]ia feed enable` | command | `feed_enable` | - | - | `imperialautomation/imperialautomation.py:370` | Enable or disable one source. |
| imperialautomation | `[p]ia feed exclude` | command | `feed_exclude` | - | - | `imperialautomation/imperialautomation.py:313` | Set comma-separated blocked keywords; use `none` to clear. |
| imperialautomation | `[p]ia feed include` | command | `feed_include` | - | - | `imperialautomation/imperialautomation.py:294` | Set comma-separated required keywords; use `none` to clear. |
| imperialautomation | `[p]ia feed interval` | command | `feed_interval` | - | - | `imperialautomation/imperialautomation.py:387` | Set polling interval from 20 to 30 minutes. |
| imperialautomation | `[p]ia feed list` | command | `feed_list` | - | - | `imperialautomation/imperialautomation.py:247` | List feed sources. |
| imperialautomation | `[p]ia feed maxitems` | command | `feed_max_items` | - | - | `imperialautomation/imperialautomation.py:405` | Set maximum posts per cycle from 1 to 3. |
| imperialautomation | `[p]ia feed priority` | command | `feed_priority` | - | - | `imperialautomation/imperialautomation.py:349` | Set source priority from 0 to 100. |
| imperialautomation | `[p]ia feed remove` | command | `feed_remove` | - | - | `imperialautomation/imperialautomation.py:276` | Remove one feed source. |
| imperialautomation | `[p]ia feed security` | command | `feed_security` | - | - | `imperialautomation/imperialautomation.py:332` | Route a source as serious security alerts. |
| imperialautomation | `[p]ia feed threadmode` | command | `feed_thread_mode` | - | - | `imperialautomation/imperialautomation.py:423` | Send normal articles into daily topic threads. |
| imperialautomation | `[p]ia music` | group | `ia_music` | - | admin/manage guild | `imperialautomation/imperialautomation.py:493` | Configure the Red Audio automation layer. |
| imperialautomation | `[p]ia music allowvoice` | command | `music_allow_voice` | - | - | `imperialautomation/imperialautomation.py:537` | Allow an additional music voice channel. |
| imperialautomation | `[p]ia music autodisconnect` | command | `music_auto_disconnect` | - | - | `imperialautomation/imperialautomation.py:636` | Set empty-channel disconnect to 180–300 seconds. |
| imperialautomation | `[p]ia music cleanup` | command | `music_cleanup` | - | - | `imperialautomation/imperialautomation.py:614` | Set deletion delay for user commands and bot responses. |
| imperialautomation | `[p]ia music denyvoice` | command | `music_deny_voice` | - | - | `imperialautomation/imperialautomation.py:553` | Remove an additional allowed music voice channel. |
| imperialautomation | `[p]ia music gate` | command | `music_gate` | - | - | `imperialautomation/imperialautomation.py:663` | Require all Audio commands to be issued in #music-request. |
| imperialautomation | `[p]ia music guide` | command | `music_guide` | - | - | `imperialautomation/imperialautomation.py:500` | Publish/update and pin the music guide. |
| imperialautomation | `[p]ia music lounge` | command | `music_lounge` | - | - | `imperialautomation/imperialautomation.py:516` | Set the shared Music Lounge. |
| imperialautomation | `[p]ia music maxqueue` | command | `music_max_queue` | - | - | `imperialautomation/imperialautomation.py:596` | Set maximum current+queued tracks per user. |
| imperialautomation | `[p]ia music panel` | command | `music_panel` | - | - | `imperialautomation/imperialautomation.py:509` | Create or refresh the current-play panel. |
| imperialautomation | `[p]ia music permissions` | command | `music_permissions_yaml` | - | - | `imperialautomation/imperialautomation.py:689` | Generate a Red Permissions ACL YAML template. |
| imperialautomation | `[p]ia music private` | command | `music_private` | - | - | `imperialautomation/imperialautomation.py:569` | Set Private Listening join-to-create trigger. |
| imperialautomation | `[p]ia setchannel` | command | `ia_set_channel` | - | admin/manage guild | `imperialautomation/imperialautomation.py:99` | Set feeds/feed-alert/music-guide/music-request/current-play. |
| imperialautomation | `[p]ia status` | command | `ia_status` | - | admin/manage guild | `imperialautomation/imperialautomation.py:142` | Show the current feed and music automation configuration. |
| imperialautomation | `[p]listen` | group | `listen` | - | guild only | `imperialautomation/imperialautomation.py:740` | Manage your Private Listening room. |
| imperialautomation | `[p]listen limit` | command | `listen_limit` | - | - | `imperialautomation/imperialautomation.py:801` | - |
| imperialautomation | `[p]listen lock` | command | `listen_lock` | - | - | `imperialautomation/imperialautomation.py:747` | - |
| imperialautomation | `[p]listen permit` | command | `listen_permit` | - | - | `imperialautomation/imperialautomation.py:853` | - |
| imperialautomation | `[p]listen rename` | command | `listen_rename` | - | - | `imperialautomation/imperialautomation.py:826` | - |
| imperialautomation | `[p]listen unlock` | command | `listen_unlock` | - | - | `imperialautomation/imperialautomation.py:778` | - |
| imperialsetup | `[p]deche` | group | `deche` | `imperialsetup`, `serverflow`, `setupserver` | guild only, guild owner/admin | `imperialsetup/imperialsetup.py:58` | Audit and finish an already partially built server. |
| imperialsetup | `[p]deche audit` | command | `audit` | `scan`, `quet` | - | `imperialsetup/imperialsetup.py:63` | Scan the existing server without changing anything. |
| imperialsetup | `[p]deche auto` | command | `auto` | `all`, `tudong` | bot permissions | `imperialsetup/imperialsetup.py:151` | Run the full preserve-first flow: reconcile -> optimize -> launch. Recommended after reviewing `[p]deche audit` and `[p]deche plan`. |
| imperialsetup | `[p]deche diagnose` | command | `diagnose` | `debug`, `chan-doan` | - | `imperialsetup/imperialsetup.py:172` | Report role hierarchy and effective per-channel permissions. |
| imperialsetup | `[p]deche launch` | command | `launch` | `start`, `khoidong` | bot permissions | `imperialsetup/imperialsetup.py:130` | Post starter content only into empty managed channels and create a readiness dashboard. |
| imperialsetup | `[p]deche optimize` | command | `optimize` | `optimise`, `toiuu` | bot permissions | `imperialsetup/imperialsetup.py:109` | Apply the recommended permissions, topics, slowmode, and category order. Only blueprint-matched roles/channels are managed. Unrecognized objects remain untouched. |
| imperialsetup | `[p]deche plan` | command | `plan` | `kehoach` | - | `imperialsetup/imperialsetup.py:69` | Show exactly what the reconciler intends to do. |
| imperialsetup | `[p]deche reconcile` | command | `reconcile` | `sync`, `dongbo` | bot permissions | `imperialsetup/imperialsetup.py:83` | Reuse/move/rename matching objects and create only missing objects. Existing channel permission overwrites and existing messages are preserved. |
| imperialsetup | `[p]deche status` | command | `status` | - | - | `imperialsetup/imperialsetup.py:243` | Display concise readiness status after setup. |
| musicstatus | `[p]musicstatus` | group | `musicstatus` | - | guild only, admin/manage guild | `musicstatus/musicstatus.py:66` | Configure the Music-Bot status and live command panels. |
| musicstatus | `[p]musicstatus commands` | command | `update_commands` | `command`, `cmds` | - | `musicstatus/musicstatus.py:126` | Refresh the live command index only. |
| musicstatus | `[p]musicstatus now` | command | `update_now` | `refresh` | - | `musicstatus/musicstatus.py:108` | Refresh both status and command panels immediately. |
| musicstatus | `[p]musicstatus reset` | command | `reset_status` | - | - | `musicstatus/musicstatus.py:135` | Delete tracked dashboard messages and clear configuration. |
| musicstatus | `[p]musicstatus setchannel` | command | `set_channel` | - | - | `musicstatus/musicstatus.py:73` | Choose the channel for both status and command panels. |
| studyops | `[p]goal` | group | `goal` | - | guild only | `studyops/studyops.py:403` | Manage today's goals. |
| studyops | `[p]goal add` | command | `goal_add` | - | - | `studyops/studyops.py:410` | Add one goal for today. |
| studyops | `[p]goal carry` | command | `goal_carry` | - | - | `studyops/studyops.py:489` | Carry unfinished goals from yesterday into today. |
| studyops | `[p]goal done` | command | `goal_done` | - | - | `studyops/studyops.py:450` | Mark one goal as completed. |
| studyops | `[p]goal list` | command | `goal_list` | - | - | `studyops/studyops.py:444` | List today's goals. |
| studyops | `[p]goal remove` | command | `goal_remove` | - | - | `studyops/studyops.py:471` | Remove one goal. |
| studyops | `[p]goal stats` | command | `goal_stats` | - | - | `studyops/studyops.py:526` | Show seven-day goal and focus statistics. |
| studyops | `[p]leetcode` | group | `leetcode` | - | guild only, admin/manage guild | `studyops/automation.py:91` | Configure automatic LeetCode reminders. |
| studyops | `[p]leetcode channel` | command | `leetcode_channel` | - | - | `studyops/automation.py:98` | Set the LeetCode reminder channel. |
| studyops | `[p]leetcode enable` | command | `leetcode_enable` | - | - | `studyops/automation.py:135` | Enable or disable automatic LeetCode reminders. |
| studyops | `[p]leetcode now` | command | `leetcode_now` | `postnow`, `test` | - | `studyops/automation.py:144` | Post the LeetCode reminder immediately. |
| studyops | `[p]leetcode schedule` | command | `leetcode_schedule` | - | - | `studyops/automation.py:117` | Set the daily LeetCode reminder time in UTC+7. |
| studyops | `[p]leetcode status` | command | `leetcode_status` | - | - | `studyops/automation.py:156` | Show LeetCode reminder configuration. |
| studyops | `[p]pomo` | group | `pomo` | - | guild only | `studyops/studyops.py:650` | Run Pomodoro focus sessions. |
| studyops | `[p]pomo pause` | command | `pomo_pause` | - | - | `studyops/studyops.py:731` | Pause your active Pomodoro. |
| studyops | `[p]pomo resume` | command | `pomo_resume` | - | - | `studyops/studyops.py:756` | Resume your active Pomodoro. |
| studyops | `[p]pomo start` | command | `pomo_start` | - | - | `studyops/studyops.py:657` | Start: `!pomo start 50 10 4 Kubernetes`. |
| studyops | `[p]pomo stats` | command | `pomo_stats` | - | - | `studyops/studyops.py:799` | Show today's and seven-day Pomodoro statistics. |
| studyops | `[p]pomo stop` | command | `pomo_stop` | - | - | `studyops/studyops.py:778` | Stop your active Pomodoro. |
| studyops | `[p]progress` | group | `progress` | - | guild only | `studyops/studyops.py:556` | Track long-term IELTS, MLOps, System, and project progress. |
| studyops | `[p]progress list` | command | `progress_list` | - | - | `studyops/studyops.py:618` | List long-term progress tracks. |
| studyops | `[p]progress remove` | command | `progress_remove` | - | - | `studyops/studyops.py:598` | Remove a progress track. |
| studyops | `[p]progress set` | command | `progress_set` | - | - | `studyops/studyops.py:563` | Set a progress track, e.g. `!progress set IELTS 45 Listening B1`. |
| studyops | `[p]room` | group | `room` | - | guild only | `studyops/studyops.py:970` | Manage your join-to-create study room. |
| studyops | `[p]room limit` | command | `room_limit` | - | - | `studyops/studyops.py:1036` | Set room user limit from 0 to 99. |
| studyops | `[p]room lock` | command | `room_lock` | - | - | `studyops/studyops.py:977` | Lock your temporary study room. |
| studyops | `[p]room permit` | command | `room_permit` | - | - | `studyops/studyops.py:1104` | Permit one member to join your locked room. |
| studyops | `[p]room rename` | command | `room_rename` | - | - | `studyops/studyops.py:1072` | Rename your temporary study room. |
| studyops | `[p]room unlock` | command | `room_unlock` | - | - | `studyops/studyops.py:1010` | Unlock your temporary study room. |
| studyops | `[p]studyset` | group | `studyset` | - | guild only, admin/manage guild | `studyops/studyops.py:117` | Configure StudyOps. |
| studyops | `[p]studyset channel` | command | `studyset_channel` | - | - | `studyops/studyops.py:144` | Set `daily`, `progress`, or `log` text channel. |
| studyops | `[p]studyset emptydelay` | command | `studyset_empty_delay` | - | - | `studyops/studyops.py:296` | Set empty temporary-room deletion delay. |
| studyops | `[p]studyset focus` | command | `studyset_focus_target` | - | - | `studyops/studyops.py:237` | Set the daily focus target in minutes. |
| studyops | `[p]studyset jointocreate` | command | `studyset_join_to_create` | - | - | `studyops/studyops.py:205` | Set the join-to-create trigger and optional target category. |
| studyops | `[p]studyset owner` | command | `studyset_owner` | - | - | `studyops/studyops.py:124` | Set the primary user for automatic daily and weekly posts. |
| studyops | `[p]studyset pomovoice` | command | `studyset_pomovoice` | - | - | `studyops/studyops.py:185` | Set the recommended Pomodoro voice channel. |
| studyops | `[p]studyset postnow` | command | `studyset_post_now` | - | - | `studyops/studyops.py:372` | Post `daily`, `review`, or `weekly` immediately. |
| studyops | `[p]studyset roomtracking` | command | `studyset_room_tracking` | - | - | `studyops/studyops.py:319` | Enable or disable voice-room time logging. |
| studyops | `[p]studyset schedule` | command | `studyset_schedule` | - | - | `studyops/studyops.py:260` | Set `morning`, `review`, or `weekly` schedule in UTC+7. |
| studyops | `[p]studyset status` | command | `studyset_status` | - | - | `studyops/studyops.py:341` | Show StudyOps configuration. |
