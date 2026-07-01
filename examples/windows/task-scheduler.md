# Windows Task Scheduler Example

Create a task that runs after login or system startup:

```text
Program/script: C:\Windows\System32\cmd.exe
Arguments: /c C:\path\to\red-cogs\examples\windows\start-red.cmd
Start in: C:\path\to\red-cogs
```

Use a dedicated Windows account where possible. Store bot credentials only in
Red's normal instance configuration, not in task arguments.

The example wrapper mirrors the common startup batch pattern of activating a
venv and running `python -O -m redbot YOUR_INSTANCE`, but keeps the real
instance name outside the repository.
