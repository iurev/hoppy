❯ hi! here's the instruction which i gave to you before. I want you to double-check all the tests which you wrote to make sure these tests are sane and they cover everything really good

  ---

  hi! i want you to read files in here;
  especially @CLAUDE.md and @guideline.md

  so: my goal in here is to do this:
  i have mjs script which manages tmux sessions;
  i want to have fully comprehensive integration tests for it, emulating user's actions inside docker container;
  so, basically like playwright tests, but for the cli tool;
  i already have several tests, BUT they are sometimes insane and incomplete;

  so, here's the list of the things you can skip if they don't work:
  you may skip key-press emulation like ctrl+shift+l, but i encourage you to at least _try_ other shortcuts, like f2 for example, or even default keys like just "w" would be enough for tests;

  i want you to look at the script, and create list of user workflows which go out from this @session-zx.mjs script in detail, like very thoroughly: including pressing backspace, etc;
  things i don't need you to test for now:
  (1) numbers for sessions: i don't use them
  (2) smart sorting of sessions
  (3) filtering sessions by capital or lower-case letters (use only one "endpoint")

  we already have tests, but they are SHIT;
  i want you to read them only for this purpose: in the plan which you make, write examples of how the code works, how to call it, it's decent, but how the logic is tested, it's pretty bad, it's
  shitty.

