Run these from the docs-handover folder after docs.tautulli.com serves the new site.

```
git clone https://github.com/Tautulli/Tautulli.wiki.git
cp wiki/*.md Tautulli.wiki/
rm Tautulli.wiki/APPLY.md
cd Tautulli.wiki
git commit -am "Point the wiki pages to docs.tautulli.com"
git push
```

The old page content stays in the wiki's git history.
