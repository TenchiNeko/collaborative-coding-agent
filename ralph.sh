#!/bin/bash
# Simple Ralph Wiggum Loop for Claude Code
while true; do
  # Run Claude in 'print mode' (-p) so it executes once and exits
  # --dangerously-skip-permissions stops it from asking 'May I run this?' every 5 seconds
  claude -p "Read TASKS.md. Do the next task. If all done, say 'DONE_EVERYTHING'. Otherwise, update TASKS.md and exit." --dangerously-skip-permissions | tee last_run.log

  # Check if Claude said it's finished
  if grep -q "DONE_EVERYTHING" last_run.log; then
    echo "Task complete! Ralph is going home."
    break
  fi

  echo "Iteration complete. Restarting Ralph..."
  sleep 2
done
