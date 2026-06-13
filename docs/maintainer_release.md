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

   `release-assets` excludes `sample__*` association folders by default. Use
   `--include-samples` only when a sample boundary should be part of the staged
   release assets.

4. Review the staged assets under `outputs/release/YYYY-MM.N/`.
5. If the release looks good, tag the commit and push tags:

   ```bash
   git tag vYYYY-MM.N
   git push --tags
   ```

   For example, release `2026-06.1` uses the tag `v2026-06.1`

6. Create a GitHub Release named with the public release asset stem, such as
   `montgomery-county-area-associations-2026-06.1`, and associate it with the
   matching `vYYYY-MM.N` tag.
7. Upload the generated PNG and TXT files from `outputs/release/YYYY-MM.N/`.

Release asset names use the project id from `config/project.yml` with
underscores converted to hyphens. Additional configured map views use their
`base_map.views` key in the public filename, so view names must be lowercase
kebab-case filename slugs.

Use `.1`, `.2`, and so on for multiple releases in the same month. Do not commit
the generated files under `outputs/`.
