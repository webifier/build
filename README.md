# Webifier Build

*Webifier Build* is a stand-alone build tool for converting any repository into a
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
