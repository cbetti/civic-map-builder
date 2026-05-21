# Maintainer Release Process

Use this when a fresh public map is worth publishing.

1. Make sure the main branch is current.
2. Run validation:

   ```bash
   civic-map-builder check
   ```

3. Render and stage release assets:

   ```bash
   civic-map-builder render
   civic-map-builder release-assets --release-name YYYY-MM.N
   ```

4. Create a GitHub Release with the same date-based name, such as `2026-05.1`.
5. Upload the PNG files from `outputs/release/YYYY-MM.N/`.

Use `.1`, `.2`, and so on for multiple releases in the same month. Do not commit
the generated files under `outputs/`.
