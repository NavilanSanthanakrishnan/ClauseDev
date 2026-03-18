## Purpose

This file tells the agent how testing must be handled during the entire software-building process.

Testing is **not** a final step. Testing must happen **after every major development step**, and again after combinations of steps, so problems are caught early and fixed immediately.

---

## Core Rule

After **every major development**, the agent must:

1. **Test from a person’s perspective**

   * Use the software like a real user would.
   * Check whether the feature works in practice.
   * Check whether the flow makes sense.
   * Check whether the result matches what the user would expect.
   * Check for visible bugs, broken UI, wrong outputs, confusing behavior, crashes, missing actions, and poor usability.

2. **Test from the code perspective**

   * Verify the implementation is logically correct.
   * Check for runtime errors, bad edge cases, incorrect state handling, broken dependencies, and integration issues.
   * Review logs, outputs, function behavior, and related code paths.
   * Confirm the new change does not break older features.

3. **If anything fails, fix it immediately**

   * Do not move on while known failures remain.
   * After fixing, run the same tests again.
   * Repeat until the feature works correctly.

4. **Retest previous working parts when needed**

   * If Step 4 affects Steps 1–3, test them together.
   * As the project grows, combine earlier tests into broader workflow tests.
   * Keep checking both isolated features and full flows.

---

## Required Testing Cycle

For every major step, the agent must follow this loop:

1. Build or modify a feature.
2. Test it from the **user perspective**.
3. Test it from the **code perspective**.
4. If it fails, debug and fix it.
5. Retest until it passes.
6. Move to the next step.
7. Periodically rerun earlier tests together as an integrated check.

This cycle must repeat throughout the entire build process.

---

## Example Workflow

* **Step 1 complete** → test Step 1
* **Step 2 complete** → test Step 2 and verify Step 1 still works
* **Step 3 complete** → test Step 3 and test Steps 1–3 together if connected
* **Step 4 complete** → test Step 4 and run broader combined tests across earlier steps

Do **not** wait until the end to do all testing.

---

## What Counts as a Major Development

A major development includes any meaningful change such as:

* Adding a new feature
* Changing existing logic
* Updating the UI
* Connecting systems together
* Refactoring important code
* Changing data flow or state handling
* Adding forms, buttons, pages, APIs, commands, automations, or integrations
* Fixing a bug that may affect behavior elsewhere

If a change meaningfully affects behavior, it must be tested immediately.

---

## User-Perspective Testing Rules

When testing from a person’s perspective, the agent should act like an end user and verify:

* The feature can actually be used
* Inputs behave properly
* Buttons, links, commands, and flows work correctly
* The output is understandable and correct
* Error messages make sense
* Navigation and interaction feel natural
* Nothing is confusing, broken, or missing

The agent should test normal use, likely mistakes, and obvious edge cases.

---

## Code-Perspective Testing Rules

When testing from the code perspective, the agent should verify:

* The feature runs without errors
* The logic behaves correctly
* Related functions still work
* Data is passed and stored correctly
* State updates correctly
* No regressions were introduced
* Dependencies and integrations still function
* Edge cases are handled safely

This may include manual checks, automated tests, logs, assertions, or direct inspection depending on the environment.

---

## Failure Handling Rules

If a test fails:

1. Stop and investigate.
2. Identify the cause.
3. Fix the issue.
4. Rerun the failed test.
5. Rerun any nearby related tests.
6. Only continue once the feature works.

The agent must not ignore failures or postpone them without a strong reason.

---

## Integration Testing Rule

As more steps are completed, the agent must also test combined flows.

Example:

* A form was created in one step
* Submission logic was added in another
* Data display was added later

Once these exist, the agent must test the full workflow from start to finish, not just each part individually.

---

## Documentation Requirement During Work

After each major step, the agent should briefly record:

* What was built or changed
* What user-perspective test was performed
* What code-perspective test was performed
* Whether it passed or failed
* What was fixed if it failed
* What was retested afterward

This keeps the build process reliable and traceable.

---

## Agent Instruction Summary

The agent must always remember:

* Test continuously, not only at the end
* Test from both the user perspective and the code perspective
* Fix failures immediately
* Retest after every fix
* Recheck older functionality as new parts are added
* Run broader integration tests as the project grows

---

## Non-Negotiable Rule

**Do not leave testing until the end.**

Testing must happen throughout the build process:

* build
* test
* fix
* retest
* continue
* combine tests
* repeat

That is the required workflow for all software development tasks.