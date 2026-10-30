# mvw-core

Single source of truth for the warehouse layout (`mvw_core.Item`, downloader, `iter_items`).

```
warehouse/<source>/<item_id>/
  meta.json   prompt.txt   original.mp4   remake.mp4   poster.webp|jpg
```

Root: `$MVW_DATA` or `<workspace>/warehouse`. meta.json has `schema`, `source`, `id`, `files{url,bytes,sha256}`, plus source fields (title, author, post_url, tags, stats, ...).
Add a new source = new `mvw-parser-<name>` repo that uses `Item`.
