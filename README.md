# Webifier

Webifier turns YAML, Markdown, HTML, notebooks, and other static content into a
static website. It is meant to remove the publishing overhead from personal
projects, research notes, notebooks, reports, and evolving documentation: decide
what content goes where, commit it, and let Webifier build a navigable site.

The core package stays small: config loading, page discovery, rendering,
extension loading, hooks, template resolution, and asset copying. First-party
renderers, templates, themes, search, comments, notebooks, and resume sections
ship as the `webifier-extensions` package, which is installed automatically with
`webifier`.

## Install

```shell
pip install webifier
```

## Build Locally

```shell
webify --index index.yml --output webified
```

For project pages, pass a base URL:

```shell
webify --baseurl my-repo --index index.yml --output webified
```

For a root domain or `<user>.github.io` site, use an empty base URL:

```shell
webify --baseurl "" --index index.yml --output webified
```

## Configure Extensions

Extensions are enabled explicitly in your site config. The instance name is local
to your site, and `uses` points to the installed extension implementation.

```yaml
config:
  webifier:
    extensions:
      site:
        uses: webifier.standard
      markdown:
        uses: webifier.markdown
      notebooks:
        uses: webifier.notebook
      search:
        uses: webifier.search
      theme:
        uses: webifier.theme
        default: system
      comments:
        uses: webifier.comments
```

Extensions can register renderers, content renderers, templates, themes, assets,
resolvers, format loaders, hooks, and config defaults. Page-aware hooks can
inspect page config and page content before injecting assets into the head,
navigation, footer, or other extension areas.

## GitHub Action

```yaml
name: Webify
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: webifier/build@main
        with:
          baseurl: ""
          index: index.yml
          publish_dir: webified
```

Deploy `webified/` with your preferred static hosting or GitHub Pages action.

## License

MIT License.
