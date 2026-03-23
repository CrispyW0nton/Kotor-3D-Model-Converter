# Trimming Repository Size (Maintainers)

The PyKotor repository is large (~380 MB pack, 118k+ objects), which can make `git clone` slow or appear to stall around 8–15%. This document describes how maintainers can **trim history** to reduce clone size and speed up clones for everyone.

## Why clones are slow

- **Large pack file**: The main object pack is ~384 MB; cloning downloads the full pack.
- **Many objects**: 118k+ objects means a lot of network round-trips and decompression.
- **Possible history bloat**: Large or binary files that were committed in the past remain in history even if removed from the working tree.

## Option 1: One-time history trim (recommended)

Use [git-filter-repo](https://github.com/newren/git-filter-repo) to rewrite history and remove large blobs. **This rewrites history and requires a force-push;** coordinate with the team and warn contributors.

### Prerequisites

```bash
# Install git-filter-repo (pick one)
pip install git-filter-repo
# or: https://github.com/newren/git-filter-repo#installation
```

### Steps

1. **Fresh clone** (filter-repo refuses to run on the main repo by design):

   ```bash
   git clone https://github.com/OldRepublicDevs/PyKotor.git PyKotor-trim
   cd PyKotor-trim
   ```

2. **Analyze** (optional) to see what’s using space:

   ```bash
   git filter-repo --analyze
   # Inspect .git/filter-repo/analysis/ (e.g. blob-shas-and-sizes.txt)
   ```

3. **Strip large blobs** from **all** history (e.g. remove blobs > 1 MiB):

   ```bash
   git filter-repo --strip-blobs-bigger-than 1M --force
   ```

   To remove only specific paths (e.g. a one-off large file):

   ```bash
   git filter-repo --path path/to/large-file --invert-paths --force
   ```

4. **Re-run GC** and check size:

   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git count-objects -vH
   ```

5. **Replace the remote** (filter-repo removes remotes) and force-push:

   ```bash
   git remote add origin https://github.com/OldRepublicDevs/PyKotor.git
   # Coordinate with team before force-push
   git push --force --all origin
   git push --force --tags origin
   ```

6. **Notify contributors**: Everyone who has cloned the repo will need to re-clone or run something like:

   ```bash
   git fetch origin
   git reset --hard origin/master
   ```

## Option 2: Prevent future bloat

- **`.gitignore`**: Keep large or generated artifacts ignored (build outputs, big binaries, etc.).
- **Git LFS**: For large assets that must be versioned, consider [Git LFS](https://git-lfs.github.com/) and add entries in `.gitattributes`.
- **CI**: Use `fetch-depth: 1` in workflows that don’t need full history to speed up checkouts.

## For contributors (no trim yet)

If the repo hasn’t been trimmed yet, use a **shallow clone** to avoid long or stuck full clones:

```bash
git clone --depth 1 https://github.com/OldRepublicDevs/PyKotor.git
cd PyKotor
```

See [CONTRIBUTING.md](../CONTRIBUTING.md#1-fork-and-clone) for more options.
