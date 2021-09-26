from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

__version__ = 'v0.0.1'
with open("webifier/__version__.py") as f:
    exec(f.read())

setup(
    name='webifier',
    packages=find_packages(include=['*', ]),  # add other exclusions in future
    version=__version__,
    license='MIT',
    description='Cook up a fully functional (semi-)static website to be served with jekyll!',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Vahid Zehtab, Ahmad Salimi',
    author_email='vahid98zee@gmail.com, ahsa9978@gmail.com',
    url='https://github.com/webifier/build',
    keywords=['webifier', 'jupyter notebook', 'markdown', 'jekyll'],
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
    ],
    entry_points={
        'console_scripts': ['webify=webifier.main:main'],
    },
    package_data={'': [
        'jekyll/search.json', 'jekyll/_includes/*.html', 'jekyll/_layouts/*.html', 'jekyll/assets/css/*.css',
        'jekyll/assets/images/*'
    ]},
)
