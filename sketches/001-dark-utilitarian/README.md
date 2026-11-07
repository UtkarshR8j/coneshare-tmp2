## Variant: Dark utilitarian

### Design stance
A faithful adaptation of the InStudy reference: icon rail + persistent folder tree + dense working surface. Tool-first, built for repeated daily use.

### Key choices
- **Layout:** 58px icon rail, 264px folder tree, flexible content. Three columns, nothing collapses.
- **Color:** `#1a1a1a` canvas, `#242424`/`#2b2b2b` panels, `#e0483a` red accent on the active rail icon and the primary Upload button only.
- **Typography:** Inter, tight tracking. Section labels are 11px uppercase with `0.08em` letter-spacing.
- **Folder tree:** `▾` disclosure triangles, folder icon, name, and a pill count badge (`.ct`). Subfolders indent 16px and are always expanded, so every count is visible without clicking.
- **Cards:** 210px minimum, 8px radius, `#2b2b2b` on `#333` border. Hover lifts 1px and lightens the border.
- **Table:** uppercase headers, 11px, hairline `#2a2a2a` row dividers, avatar + username + email stacked in the User column.
- **Interaction:** clicking a tree node selects it and fires a toast; the Folders/Tags toggle switches; Upload fires a toast.

### Trade-offs
- **Strong at:** information density, matching the reference exactly, scannability of counts at a glance.
- **Weak at:** the icon rail costs 58px and currently has no labels, which is a discoverability risk. The three-column layout is tight under 1280px.

### Best for
Admins who live in this screen all day and need many folders visible simultaneously.
