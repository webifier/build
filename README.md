# Webifier

<p align="center">
  <a href="#how-to-use">How to Use</a> •
  <a href="https://webifier.github.io/">Docs</a> •
  <a href="#license">License</a>
</p>

<p align="center" markdown="1">
    <a href="https://github.com/webifier/build/actions/workflows/python-publish.yml" >
        <img src="https://github.com/webifier/build/actions/workflows/python-publish.yml/badge.svg" alt="Webify & Deploy">
    </a>
</p>

Webifier is a stand-alone build tool for converting any repository into a deployable [jekyll](https://jekyllrb.com/)
website. You can define your pages via `yaml` files and provide notebooks, markdown and pdf and other files for Webifier
to render. It uses [python markdown](https://python-markdown.github.io/)
providing additional control over attributes and other extensive functionalities. It lets you define and direct how your
web pages feel and automatically manages your assets, making it a perfect solution for fast static website development
and a straightforward tool for creating Github pages as a Github action. Webifier is a good fit for the missing puzzle
piece of collaborative content creation on Github and is a great tool for sharing educational material on the web.

Webifier lets you communicate with your audience through comments with the help of [utterances](https://utteranc.es/)
and track their engagement through [Google Analytics](https://analytics.google.com/). It also automatically creates a
static search engine with the help of [Jekyll-Simple-Search](https://github.com/christian-fei/Simple-Jekyll-Search). And 
as a cherry on the cake, you can provide custom [jinja2](https://jinja.palletsprojects.com/en/3.0.x/) templates if 
the built-in ones do not satisfy your needs. Plus, you can change the behavior of the rendering stage of Webifier by 
providing your custom implementation of  `assets`, `_includes`, and `_layouts` in your repository.

## How to Use

### Locally

In order to see how your webified pages look before you send it out to the world, you might want to build and serve them
locally. For this you would need both webifier and jekyll installed.

1. [Install Jekyll](https://jekyllrb.com/docs/installation/).
2. Install **webifier** from PYPI (webifier uses `python>=3.8` therefore you might need
   to [install an appropriate python version](https://www.python.org/downloads/) beforehand):
   ```shell
   pip install webifier
   ```
3. Change your working directory to where your website resides and Webify everything (assuming your initial index file
   is `index.yml`, and you want the results to go to `webified`)
   ```shell
   # cwd should be where your files are
   webify --index=index.yml --output=webified
   ```
4. Change your working directory to the webified results and serve jekyll:
   ```shell
    cd webified
    jekyll serve
    ```
   You can now access your website from `localhost:4000` by default.

### Github

Using Webifier for your repositories is as simple as adding it as a step in your deployment workflow. After checking out
your desired repository, add the Webifier action and change the default values for `baseurl`, `repo`, and `index` input
variables to your needs. After that you are good to deploy your Webified website for which there are a number of great
actions available.

Your workflow might look something like follows. We are using
[peaceiris/actions-gh-pages](https://github.com/peaceiris/actions-gh-pages) deploy action as an example here and you can
replace it with any other deployment action or even push the webified results into a separate github branch manually.
Keep in mind that because the results are pushed to a separate branch, you might need to change the Github Pages source
branch from your repository settings under the Pages section.

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
        uses: webifier/build@master # or select a desired version

      # the deploy action is in charge of pushing back the 
      #     webified files into a separate branch such as `gh-pages`
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3 # or use any other jekyll deploy action
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          enable_jekyll: true
          publish_dir: ./webified/
```

Note that if you wish to webify a `<name>.github.io` repository or do not wish to have the content of your repository to
be referred to with a `/<repository-name>/` slug, you should provide `baseurl: ''` to the webifier action. It is highly
suggested that you consult the [documentations](https://webifier.github.io/) for further details of the nuts and bolts
of webifiable materials. You can also look at the documentations'
[code](https://github.com/webifier/webifier.github.io) which itself is built using Webifier and greatly showcases its
functionalities.

## License

MIT License, see [webifier/build/LICENSE](https://github.com/webifier/build/blob/master/LICENSE).

## Todo

There are a number of improvements that can enlarge Webifier's usability. What follows is a list of the ideas that we
have in mind, feel free to suggest your ideas by opening up a feature request issue.

* **Print content**: add automatic print (and export as pdf) functionality for content content (markdown/notebook)
  pages.
* **Table of Content**: add automatic creation of a customizable multi-level table of content for all pages.

  
