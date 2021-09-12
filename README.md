# Webifier Build

<p align="center">
  <a href="#how-to-use">How to Use</a> •
  <a href="https://webifier.github.io/">Docs</a> •
  <a href="#license">License</a>
</p>

Webifier Build is a stand-alone build tool for converting any repository into a
deployable [jekyll](https://jekyllrb.com/) website. You can define your pages as `yaml` files and provide notebooks,
markdown and pdf files for Webifier to render. Webifier uses [python markdown](https://python-markdown.github.io/)
providing additional control over attributes and other extensive functionalities. It lets you define and direct how your
web pages feel and automatically manages your assets, making it a perfect solution for fast static website development
and a straightforward tool for creating Github pages as a Github action. Webifier is a good fit for the missing puzzle
piece of collaborative content creation on Github and is a great tool for sharing educational material on the web.

Webifier lets you communicate with your audience through comments with the help of [utterances](https://utteranc.es/)
and track their engagement through [Google Analytics](https://analytics.google.com/). You can change the behavior of
both the rendering and build stages of Webifier by providing your custom implementation of `build`, `assets`
, `_includes`, and `_layouts` in your repository.


## How to Use

Using Webifier is as simple as adding it as a step in your deployment workflow. After checking out your desired
repository, add Webifier action and change the default values for `baseurl`, `repo`, and `index` input variables to your
needs. After that you are good to deploy your Webified website for which there are a number of great actions available.

Your workflow might look something like follows. We are using
[peaceiris/actions-gh-pages](https://github.com/peaceiris/actions-gh-pages) deploy action as an example and you can
replace it with any other deployment action or even push the webified results into a separate github branch manually.

```yaml
name: Webify & Deploy

on:
  push:
    branches: [ master ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      # you need to checkout your code before webifying
      - name: Checkout
        uses: actions/checkout@v2

      - name: Webify
        uses: webifier/build@master # in order to get the last code specify branch name or else specify intended version
        #with:
        # baseurl: '' # if you are webifying a `<name>.github.io` repository or don't wish to have the content of this 
        #              # repository to be referred to with a "<repository-name>/" slug

      # the deploy action is in charge of pushing back the webified files into a separate branch such as `gh-pages`
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3 # you can use any other jekyll build action instead
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          enable_jekyll: true
          publish_dir: .
```
We suggest that you consult the [documentations](https://webifier.github.io/) for further details of the nuts and bolts 
of the webifiable materials. You can also look at the documentations' 
[code](https://github.com/webifier/webifier.github.io) which itself is built using Webifier and greatly showcases its
functionalities.

## License
MIT License, see [webifier/build/LICENSE](https://github.com/webifier/build/blob/master/LICENSE).

## Todo

There are a number of improvements that can enlarge Webifier's usability. What follows is a list of the ideas that we
have in mind, feel free to suggest your ideas by opening up a feature request issue.

* [x] **Inline Link Definition**: enable automatic processing of index/content links mentioned in markdown or notebook
  texts.
* [x] **Search**: add automatic (full-text) search functionality for index and content (markdown/notebook) pages.
* [ ] **Print content**: add automatic print (and export as pdf) functionality for content content (markdown/notebook)
  pages.
* [ ] **Table of Content**: add automatic creation of a customizable multi-level table of content for all pages.

  
