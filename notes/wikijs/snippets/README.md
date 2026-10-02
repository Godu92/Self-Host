# 📄 Auto-generate Subpage Tree for Wiki.js 2.x

## Description

This script dynamically loads and displays a hierarchical list of subpages in Wiki.js (version 2.x). It utilizes the built-in GraphQL API (`pages.search` for subpaths, `pages.list` for root-level) to fetch pages and builds a nested tree view up to a specified depth.

## Usage

The script can be included in two ways:

1. **Globally** via **Administration → Theme → Head HTML Injection**

## Requirements

A `<div class="children-placeholder">` must be present on the page. Configure it with the following optional attributes:

| Attribute          | Default          | Description                                                                                                                                       |
| ------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data-limit`       | `100`            | Maximum number of subpages                                                                                                                        |
| `data-depth`       | `2`              | Maximum tree depth                                                                                                                                |
| `data-sort`        | `path:asc`       | Sorting field (`path`, `title`, `description`) and direction (`asc`, `desc`)                                                                      |
| `data-target-path` | _(current page)_ | Override target path. Supports locale prefix (e.g. `de/projekte/project01`). Set to locale only (e.g. `de`) to generate a full sitemap from root. |
| `data-debug`       | `false`          | Enable debug logs in the browser console                                                                                                          |

## Examples

Subpages of the current page:

```html
<div class="children-placeholder" data-depth="2"></div>
```

Subpages of a specific path:

```html
<div class="children-placeholder" data-target-path="de/projekte/project01" data-depth="3"></div>
```

Full sitemap (all pages):

```html
<div class="children-placeholder" data-target-path="de" data-depth="5" data-limit="200"></div>
```

## Result

Once loaded, the script replaces the placeholder with a nested `<ul>` structure of links to all matching subpages.
