# Example 1: moving non-typical attributes onto a separate tab

Real-world case from a 1C developer. The source prompt was a short note; the improved version is a structured spec for an implementer.

## Before

```
Task — display all non-typical attributes of typical objects on the
"Доп. реквизиты Айс" tab. Place the tab last. If only one attribute is
added, Айс_КодИсточника77, do nothing. Prepare a list of objects,
analyze element forms, determine where and how to add the tab.
```

## After

```
Analyze all typical configuration objects and prepare a list of those
that contain non-typical attributes. Study the element forms of these
objects. Add a new "Доп. реквизиты Айс" tab last in order to each form.
Move all non-typical attributes onto the tab, except when the only
non-typical attribute is Айс_КодИсточника77 (then no changes are made).
For each object, specify:

1. Object name.
2. List of non-typical attributes.
3. Name of the element form used and current tab structure.
4. Recommended changes to tab placement and attribute movement, taking
   interface logic into account.

Format the output as a convenient table or structured list ready for
implementation.
```

## What changed

1. **Imperative form.** "needs to be displayed" and "should be moved" replaced with active "Display", "Move".
2. **Goal in the first sentence.** "Analyze all typical objects... prepare a list" sets the goal immediately, without preamble.
3. **Analysis steps numbered by meaning.** First — analysis (typical objects, element forms), then result formation.
4. **Edge case extracted separately.** Instead of a parenthetical insert "if only one attribute is added...", a full sentence with the construction "except when ..." was produced.
5. **Terms preserved verbatim.** Айс_КодИсточника77, "Доп. реквизиты Айс", "non-typical attributes" carried over without changes.
6. **Expected output format stated explicitly.** "convenient table or structured list" and a numbered list of fields per object.
7. **No new requirements.** No mentions of tests, documentation, rollback, access rights — none of which were in the source text.
