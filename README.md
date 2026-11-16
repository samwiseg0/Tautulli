# Moving the Tautulli docs to docs.tautulli.com

The wiki is now a Docusaurus site. It lives in `website/` on the branch
`samwiseg0/doc-to-docusaurus` in samwiseg0/Tautulli. You can look at it here:
https://samwiseg0.github.io/Tautulli/

Cloudflare Pages builds it from `Tautulli/Tautulli` on the free plan.

- `master` publishes https://docs.tautulli.com.
- `nightly` publishes https://docs-nightly.tautulli.com, with a notice bar that says so.
- Any other branch pushed to `Tautulli/Tautulli` gets a preview URL.

Setup is about ten steps in the Cloudflare dashboard and one app install on GitHub. Visitors keep
reaching the current GitBook site until step 9.

## In this folder

- `README.md` is this guide.
- `check-docs-site.sh` checks a docs site with `curl` and prints one `ok` or `FAIL` line per
  check. Run it after the steps that say so.
- `wiki/` holds a replacement body for every wiki page. Each one links to its new page.
  `wiki/APPLY.md` has the commands to push them.

Two branches in samwiseg0/Tautulli go with it. Each is one commit on `nightly`.

- `tfix/bug-export-level-9-custom-fields` (`9ec363df`). Take this one first. See below.
- `samwiseg0/docs-links` (`3dd936fa`). It points the wiki links in the app at
  docs.tautulli.com. Take it after the site is live.

## Before you start

You need access to the `tautulli.com` zone in Cloudflare, and an owner of the `Tautulli`
organization on GitHub to install one app.

Cherry-pick `tfix/bug-export-level-9-custom-fields` (`9ec363df`) before the docs branch. The docs
build writes the Exporter Guide field tables from `build_export_docs()`, the function behind
`/exporter_docs`. That function ticks Level 9 on 10 rows where it is wrong. The rows are
`artFile`, `logoFile`, `squareArtFile`, and `thumbFile` on episodes and clips, and `locations` on
shows and artists. The same bug makes the export modal disable those fields at Level 9. The fix
corrects both.

## Steps

Do them in this order.

1. In Cloudflare, open Workers & Pages. Select Create application > Pages > Connect to Git >
   GitHub.
2. GitHub opens. Install the Cloudflare Workers and Pages app on the `Tautulli` organization.
   Under Repository access, select Only select repositories and pick `Tautulli/Tautulli`.
   Authorize the app for your own user when GitHub asks.
3. Back in Cloudflare, select `Tautulli/Tautulli` and Begin setup. Set these values.

   | Setting | Value |
   | --- | --- |
   | Project name | `tautulli-docs` |
   | Production branch | `master` |
   | Framework preset | Docusaurus |
   | Build command | `npm run build` |
   | Build output directory | `build` |
   | Root directory (advanced) > Path | `website` |
   | Environment variables | none |

   Select Save and Deploy. The first build runs on `master` and fails, because `master` has no
   `website/` folder yet. Visitors see no change.

   If the project name is taken, Cloudflare adds a suffix. Use the real name wherever this guide
   says `tautulli-docs`.
4. Open the project > Settings > Builds. Set these values.

   | Setting | Value |
   | --- | --- |
   | Build watch paths, Include | `website/*`, `plexpy/api2.py`, `plexpy/exporter.py`, `plexpy/webserve.py` |
   | Build watch paths, Exclude | empty |
   | Production branch | `master`, automatic production deployments on |
   | Preview branches | Custom branches. Include `*`. Exclude `dependabot/*` |
   | Build system version | v3 |

5. Merge the docs branch into `nightly`. Pages builds `nightly`. When the build finishes,
   https://nightly.tautulli-docs.pages.dev serves the nightly docs.
6. In the project, open Custom domains > Set up a custom domain. Enter
   `docs-nightly.tautulli.com`. Select Continue, then Activate domain. Cloudflare adds a CNAME
   `docs-nightly` to `tautulli-docs.pages.dev` in the `tautulli.com` zone.
7. Open the `tautulli.com` zone > DNS > Records. Edit the `docs-nightly` CNAME. Set the target
   to `nightly.tautulli-docs.pages.dev`. Keep it Proxied (orange cloud). Wait until Custom
   domains shows the domain as Active. Then open https://docs-nightly.tautulli.com/ and check
   that it shows the notice bar.

   A DNS-only record here sends visitors to the `master` build, so keep it Proxied.
8. Wait for the docs to reach `master` at the next release. Pages builds production at
   https://tautulli-docs.pages.dev. Check it before the domain moves:

   ```
   ./check-docs-site.sh --no-nightly https://tautulli-docs.pages.dev
   ```

   Expect one `FAIL`, on the sitemap line. The sitemap already lists docs.tautulli.com, which is
   correct.
9. In Custom domains, select Set up a custom domain and enter `docs.tautulli.com`. The zone
   already has a `docs` CNAME to `hosting.gitbook.io`. If Cloudflare offers to update it, accept.
   If it reports a conflict, edit the `docs` record in DNS > Records. Set the target to
   `tautulli-docs.pages.dev` and set it to Proxied. Then activate the domain again.

   Visitors move from GitBook to Pages within 5 minutes, the TTL of the old record. Keep the
   custom domain in GitBook until step 10 passes.
10. Check both sites:

    ```
    ./check-docs-site.sh
    ```

    Every line should say `ok`. With no arguments the script checks docs.tautulli.com and
    docs-nightly.tautulli.com.

## Two things to keep in mind in Cloudflare

- Keep the `docs` and `docs-nightly` records Proxied. tautulli.com sends HSTS with
  `includeSubDomains` and `preload`, so a browser refuses either name if it ever gets a wrong
  certificate. The zone certificate covers `*.tautulli.com` and answers from the first request
  on a Proxied record.
- Check that no Cache Rule or Page Rule matches `docs` or `docs-nightly`. A zone cache rule can
  serve an old page after a deployment and can hide the redirects.

## How nightly and master work

`nightly` fast-forwards into `master` at release, so both branches hold the same files. The site
config reads the branch name that Cloudflare passes to the build. It sets the URL, the notice
bar, and `noindex` from that. A release needs no docs edit, and there is no setting per branch
in the dashboard.

| Branch | URL | Search engines | Notice bar |
| --- | --- | --- | --- |
| `master` | docs.tautulli.com | indexed | no |
| `nightly` | docs-nightly.tautulli.com | `noindex` | yes, links to the released docs |
| any other | its own preview URL | `noindex` | no |

Pull requests target `nightly`. A merged docs change shows on docs-nightly.tautulli.com at once
and reaches docs.tautulli.com at the next release. You can let a fix wait for the release. You
can also cherry-pick a docs-only commit to `master`, which publishes it at once. That puts a
commit on `master` that `nightly` lacks, so the next release cannot fast-forward.

Edit this page opens the file on `nightly`, for the same reason.

## What previews cover

- A branch pushed to `Tautulli/Tautulli` builds a preview when the push touches the watch
  paths. Each build gets a fixed URL such as `https://<hash>.tautulli-docs.pages.dev`. The
  branch also gets `https://<branch>.tautulli-docs.pages.dev`, which follows its newest build.
- When that branch has a pull request, the Cloudflare app comments with both URLs and adds a
  "Cloudflare Pages" check.
- Pull requests from forks get no preview and no comment. Cloudflare lists this as a known
  issue. They still get the "Build Docs" check on GitHub, which fails on a build error, a broken
  link, or a broken anchor. To see a fork pull request rendered, check it out and run
  `npm start` in `website/`.
- A fork preview would need a workflow that holds a Cloudflare API token and uploads files that
  a fork built. A stray `_worker.js` in those files would run as server code under the project.
  The branch does not add that.

## After the site is live

- GitBook. Remove the custom domain there and unpublish the space. Old GitBook links keep
  working, because `website/static/_redirects` sends the 16 old paths to the new pages. If the
  space still syncs to the `docs` branch, turn that off too.
- App links. Cherry-pick `samwiseg0/docs-links` (`3dd936fa`). It changes the 12 wiki links in
  the app, plus `README.md`, `API.md`, the issue template, and the help URL in the Flatpak
  metainfo. The Flathub copy of the metainfo needs the same one-line change. The old links
  followed `GIT_USER` and `GIT_REPO`, so a fork install opened its own wiki. Now every install
  opens docs.tautulli.com.
- Wiki. Push the files in `wiki/` with the commands in `wiki/APPLY.md`. Keep the wiki itself,
  because released versions link to it. The old text stays in the wiki's git history.

## Day to day

- Edit a page in `website/docs/` and merge to `nightly`. docs-nightly.tautulli.com republishes
  itself. The next release republishes docs.tautulli.com.
- The API reference and the Exporter Guide field tables are written by the build. A merged
  change to an API docstring, or to `plexpy/exporter.py`, republishes them. Nobody pastes them
  by hand any more.
- To preview locally, run `npm ci` and `npm start` in `website/`. It needs Node 20 or newer and
  Python 3.11 or newer.
- The build fails on a broken link or a broken anchor, so a pull request shows it before merge.
- Build logs are under the project > Deployments. To undo a bad release, roll back to an earlier
  production deployment there.
- The free plan allows 500 builds a month and one build at a time. The watch paths skip pushes
  that do not touch the docs. A push with 20 or more commits builds anyway.
- `npm audit` reports issues in build-time packages. None of that code ships in the site.
  Dependabot can cover them if you add an `npm` entry for `/website`.

## If something goes wrong

Nothing has run on Cloudflare yet. The build, the three branch cases, the redirects, and the 404
page were tested locally with `wrangler pages dev` and with Cloudflare's variables set by hand.
These are the points only a real build can settle, with what to do for each.

- The first `nightly` build fails in `generate-docs.py` with an import error. The build runs in
  `website/` and reads `plexpy/` and `lib/` one level up. Cloudflare's docs do not say that
  works. If it does not, clear Root directory, set the build command to
  `cd website && npm ci && npm run build`, and set the output directory to `website/build`.
  Then also set `NODE_VERSION` to `24` under Settings > Variables and Secrets, because
  Cloudflare no longer finds `website/.nvmrc`.
- The build log shows a Node version other than 24, or the install fails on `.nvmrc`. Delete
  `website/.nvmrc` and set `NODE_VERSION` to `24` under Settings > Variables and Secrets, for
  Production and Preview.
- A docs push does not start a build. Cloudflare's docs do not say whether the watch paths
  start at the repo root or at the Root directory. Clear the watch paths. Every push then
  builds, which costs more of the 500 monthly builds.
- Step 9 shows errors for a few minutes. Cloudflare's docs do not say what Set up a custom
  domain does when the name already has a record. Step 9 covers both cases.
- GitBook still answers on docs.tautulli.com after Pages shows the domain as Active. GitBook
  serves the name through its own Cloudflare hostname, which can take priority. Remove the
  custom domain in GitBook.
- docs-nightly shows a redirect loop. Check the zone SSL/TLS mode first.

## Reference

What the docs branch adds:

- `website/` holds the site. `website/docs/` holds the pages, converted from the wiki and
  corrected against v2.19.1.
- `website/generate-docs.py` writes the API reference and the Exporter Guide field tables on
  every build, with no running Tautulli. The prose of the Exporter Guide is in
  `website/docs/_exporter-guide.md`.
- `website/docusaurus.config.js` holds the branch logic described above.
- `website/static/_redirects` holds the redirects for the old GitBook paths.
- `website/.nvmrc` sets Node 24 for the Cloudflare build. The build image already has
  Python 3.13.
- `.github/workflows/docs-build.yml` builds the site on pull requests that touch `website/**`,
  `plexpy/api2.py`, `plexpy/webserve.py`, or `plexpy/exporter.py`. It deploys nothing.

Where things stand today:

- `docs.tautulli.com` is a DNS-only CNAME to `hosting.gitbook.io` and serves a GitBook site.
- `tautulli.com` is on the Cloudflare free plan, proxied to GitHub Pages.
- `docs-nightly.tautulli.com` does not exist yet.

Wiki pages and their new paths:

| Wiki page | New path |
| --- | --- |
| Home | `/` |
| Installation | `/installation` |
| Asking-for-Support | `/asking-for-support` |
| Debugging | `/debugging` |
| Frequently-Asked-Questions | `/frequently-asked-questions` |
| Notification-Agents-Guide | `/notification-agents-guide` |
| Custom-Notification-Conditions | `/custom-notification-conditions` |
| Custom-Scripts | `/custom-scripts` |
| 3rd-Party-APIs-Guide | `/3rd-party-apis-guide` |
| Exporter-Guide | `/exporter-guide` |
| Tautulli-API-Reference | `/api-reference` |
| Upgrading-to-Python-3-(Tautulli-v2.5) | removed, see `/installation` |
