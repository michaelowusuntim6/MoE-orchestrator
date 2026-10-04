# Upstream tracking

This copy of LoFT is **vendored** into the MoE-orchestrator repository: the
nested `.git` was removed so the parent commit contains the sources.

- Upstream: https://github.com/diptanshu1991/LoFT
- Vendored at commit: `32fa65a` ("Update README.md")
- Bug fixes applied after vendoring: see `../docs/LoFT_KNOWN_BUGS.md`
  (14 bugs, all fixed 2026-10-04).

Upstream tracking is manual. To re-sync:

```bash
cd /tmp && git clone https://github.com/diptanshu1991/LoFT.git loft-upstream
diff -r /tmp/loft-upstream /home/mike/MoE-orchestrator/LoFT
```
