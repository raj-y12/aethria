# Memo Ruling Inline Gate Design

## Goal

Make the memo's `Commit Ruling` area read as a deliberate workflow with a clear prerequisite, so users understand that high-risk deals require explicit acknowledgement before a final ruling can be committed.

## Approved Direction

Use an inline gate, not a blurred lockout:

- Keep the ruling controls visible at all times.
- Disable the final `Commit ruling` action until the risk review acknowledgement is completed.
- Replace the vague `Mark reviewed` button with explicit acknowledgement copy.
- Restyle the section so the gate reads as part of the ruling workflow, not a detached utility control.

## Interaction Design

When risk acknowledgement is required:

- The decision choices and rationale input remain visible and editable.
- A dedicated gate block appears inside the ruling panel above the commit action.
- The gate copy explains why the action is locked.
- The acknowledgement control uses explicit confirmation language.
- The final action row stays visible but visually muted until the acknowledgement is complete.

When acknowledgement is complete:

- The gate shifts to a confirmed state.
- The final action row regains full contrast.
- The user can commit the ruling if the other form requirements are satisfied.
