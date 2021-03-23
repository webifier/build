<div style="text-align: justify">

# SUT AI Lecture Notes

An automatic static-site generator for jupyter notebook files.

The lecture notes of Artificial Intelligence course at Sharif University of Technology. See https://sut-ai.github.io/LectureNotes/

## Contribution in Lecture Notes

> The following instructions describe how to contribute.

1. Assume you want to add *Chapter 1 - Intelligent Agents* lecture note. Then, you have a `.ipynb` file and maybe some other resources such as images.

1. Create a fork of this repository.

1. Create a directory inside `notebooks`. **(IMPORTANT: Note that the name of this directory shouldn't contain whitespaces.)**

    ```bash
    cd notebooks
    mkdir IntelligentAgents
    ```

1. Put your notebook and resource files in the above directory.

1. Rename your notebook file to `index.ipynb`.
    
    ```bash
    mv some_nb.ipynb index.ipynb
    ```

1. Add your notebook directory name which you have created at step 3 to `_data/content.yml` as shown below.

    ```yaml
    ...
      notes:
        ...
        - title: Intelligent Agents
          notebook: IntelligentAgents # Add this line
        ...
    ...
    ```

1. Create `authors` directory in your notebook directory.
    
    ```bash
    cd notebooks/IntelligentAgents
    mkdir authors
    ```

1. Add **SQUARE** images of each author with a maximum size of **1.5MB** to the `authors` directory.

1. Add `metadata.yml` and write authors information as shown bellow. (Icons can be any font-awesome free icon. See https://fontawesome.com/icons?d=gallery)

    ```yaml
    - name: Author 1
      image: author1.png
      role: Author 1 role
      contact:              # This section is optional
        - icon: fas fa-at
          url: mailto:the_email@gmail.com
        - icon: fab fa-github
          url: https://github.com/

    - name: Author 2
      image: author2.png
      role: Author 2 role
      contact:
        - icon: fab fa-linkedin
          url: https://linkedin.com/
        - icon: fab fa-telegram
          url: https://telegram.me/
    ```

1. Create a pull request from your fork to the `master` branch of this repository, and wait for reviewers to approve your changes or make changes if they request more changes. Note that some checks will be done in your pull requests which you must pass **required** ones. If you fail one of them, check error message and try to fix the problem.

Check out `notebooks/Example` as a sample of a lecture note files.

Thank you for your contribution.

</div>
