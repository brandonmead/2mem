# Quickstart: using your 2mem

Your 2mem is a **second memory**: a private notebook of what you know and have decided, kept as
plain documents in your own GitHub repository. You and Claude both read it before advising and
write to it afterwards, and an automatic check reads every change before it is saved.

This page assumes [SETUP.md](SETUP.md) is done and Claude is connected.

## Ask Claude

Open your 2mem Project in Claude (claude.ai or Claude Desktop) and say what you want in your own
words. You don't need to say where it goes or what kind of document it is: Claude decides.

- "Remember that the furnace filter is 16x25x1 and gets changed every three months."
- "Write down how I winterize the garden hose, step by step."
- "We chose the smaller car. Note why, and what else we looked at."
- "Add notes from today's physiotherapy appointment: new exercises, next visit in four weeks."
- "The passport fee went up. Update the renewal steps."
- "Save this article about sourdough exactly as written. It's from a bakery's blog."
- "What do I have on file about my vaccinations?"
- "What did we decide about the school, and why?"

If Claude isn't sure whether something is a new document or belongs in an existing one, it asks.

## What happens next

1. Claude proposes the change as a **pull request** and gives you its link.
2. The automatic check (`okf-lint`) reads it, usually within a minute or two.
3. If it passes, the change is **saved automatically**. You don't click anything. Claude tells you
   when it has landed.

To see it on github.com, open your repository and browse the folders, or open the **Pull
requests** tab: merged ones are under **Closed**, each with what changed and why.

## When a change doesn't go through

- **Red check ("problems to fix").** The check found something wrong. Nothing has been saved. A
  comment on the pull request lists the problems. Claude usually fixes them itself. If it asks you
  something, for example "this removes a lot of text, is that intended?", answer it.
- **"Passed the check, held for a person."** The change is fine but needs you to merge it. This
  happens when it changes the rules of your knowledge base (such as your list of areas), or has
  the `hold` label. Open the link, look at **Files changed**, then click **Squash and merge**, or
  **Close pull request** if you don't want it.
- **"The document check could not run."** The check itself had a hiccup. Open the **Actions** tab,
  find the run, and click **Re-run jobs**.

## Undo a change

- **Ask Claude:** "Undo the change you made to the furnace filter note." It proposes a new change
  that puts the old text back, and the check reads it like any other.
- **On github.com:** open the merged pull request and click **Revert**. That opens a new pull
  request that undoes it. If undoing removes a whole document or a large part of one, the check
  refuses until you add the `allow-loss` label to that pull request, which is how you confirm the
  removal is intended.

Nothing is truly lost: every earlier version stays in the repository's history.

## Editing it yourself

- **On github.com:** open a file, click the pencil, then **Commit changes → Propose changes**. It
  becomes a pull request and goes through the same check.
- **In Obsidian (optional):** a note-taking app that can edit your 2mem like a folder of notes.
  Set it up with [SETUP.md step 10](SETUP.md#10-edit-in-obsidian-optional).

## For the curious

- [`_meta/conventions.md`](../_meta/conventions.md): every rule the check applies. It is the single
  source of truth.
- [`claude-instructions.md`](claude-instructions.md): exactly what Claude is told to do.
