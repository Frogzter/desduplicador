# TODO - Fixes from code review

- [x] Refactor `static/js/app.js` to remove inline dynamic action handlers and use event delegation.
- [x] Harden DOM access with null checks across UI update points.
- [x] Simplify/centralize keep-selection state handling.
- [x] Add API timeout/cancellation and improved error normalization.
- [x] Improve load-time error surfacing with toasts for user-visible failures.
- [x] Rework filter rendering to avoid unsafe direct HTML interpolation for category names.
- [x] Review `templates/index.html` static resource references and fix the 404 resource issue.
- [ ] Run thorough validation of updated UI flows and interactions.
