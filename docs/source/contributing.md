# Contributing

Contributions are welcome, and appreciated! 
Takes a team to build quality software.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at https://github.com/powderflask/django-signoffs/issues.

If you are reporting a bug, please include:

-   Your python / django / signoffs and versions.
-   Any details about your local setup that might be helpful in troubleshooting.
-   Detailed steps to reproduce the bug (ideally a minimal example)

### Fix Bugs, add Features

GitHub issues tagged with "bug" or "enhancement" and "help
wanted" are open and looking for a programmer.

### Improve the Documentation

django-signoffs could always use better documentation, whether as part of the
official django-signoffs docs, in docstrings, or even on the web in blog posts,
articles, and such.  If you post an article or how-to, let us know for a backlink.

### Submit Feedback

The best way to send feedback is to file an issue at https://github.com/powderflask/django-signoffs/issues.

If you are proposing a feature:

  - Explain in detail how it would work.
  - Keep the scope as narrow as possible, to make it easier to implement. 
  - Remember that this is a volunteer-driven project, and that contributions
    are welcome :)

## Get Started!

Ready to contribute? Here's how to set up for local development.

1.  Fork the [django-signoffs](https://github.com/powderflask/django-signoffs) repo on GitHub.

2.  Clone your fork locally:

    ``` shell
    $ git clone git@github.com:your_name_here/django-signoffs.git
    ```

3.  Create a Python virtualenv and install dev dependencies:

    ``` shell
    $ cd django-signoffs/
    $ activate your_virtual_env_here  # depending on venv tool
    $ pip install -r dev_requirements.txt
    ```

4.  Create a branch for local development:

    ``` shell
    $ git checkout -b name-of-your-bugfix-or-feature
    ```

    Go nuts!

5.  Before committing, lint and test:

    ``` shell
    $ tox
    ```

    If your code fails isort or black checks:
    ``` shell
    $ isort signoffs tests
    $ black signoffs tests
    ```
    
    If you updated docs, check they build successfully:
    ``` shell
    $ pip install -r docs/requirements_docs.txt
    $ invoke docs.build
    ```
    Open `docs/build/html/index.html` in browser to review your new docs!
    
6.  Commit your changes and push your branch to GitHub:

    ``` shell
    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature
    ```
    
7.  Submit a pull request via GitHub

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. All `tox` tests must pass
2. Bug fixes and new features should include tests.
3. If the pull request adds/modifies functionality, add/update docs. 
    Ensure all functions and classes have a complete docstring.
    Add any new features to the list in README.md

## Tips

To run a subset of tests:

``` shell
  $ pytest -k "my_test"
```

## Deploying

A reminder for the maintainers on how to deploy.

### Docs
GitHub webhook deploys docs to ReadTheDocs every commit.

### PiPy
``` shell
$ bumpver --minor # possible: --major / --minor / --patch
$ invoke pypi.release  # to testpypi
$ invoke pypi.release --repo=pypi
```

