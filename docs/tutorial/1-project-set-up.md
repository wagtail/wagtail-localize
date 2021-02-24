# 1. Project Set up

Welcome to the tutorial!

In this section, you will set up a very basic Wagtail instance.

=== "Mac OS and GNU/Linux"

    **Create a project**

    Open a terminal and run the following commands to create a new site called ``tutorial``:

    ``` shell
    # Create a new virtual environment in a 'tutorial-venv' folder
    # This isolates installed dependencies from other projects
    python3 -m venv tutorial-venv

    # Activate the virtual environment
    # Note: If you come back to this tutorial later, you will need to
    # run this again to reactivate the environment
    source ./tutorial-venv/bin/activate

    # Install Wagtail and Wagtail Localize
    pip install wagtail wagtail-localize

    # Start a new project
    wagtail start tutorial
    cd ./tutorial
    ```

=== "Windows"

    Before you start, make sure you have Python 3.7 or greater installed, you can find this in the [Microsoft Store](https://www.microsoft.com/en-us/p/python-39/9p7qfqmjrfp7).

    **Create a project**

    Open a new PowerShell window and run the following commands:

    ``` powershell
    # Create a new virtual environment in a 'tutorial-venv' folder
    # This isolates installed dependencies from other projects
    python -m venv tutorial-venv

    # Activate the virtual environment
    # Note: If you come back to this tutorial later, you will need to
    # run this again to reactivate the environment
    .\tutorial-venv\Script\Activate.ps1

    # Install Wagtail and Wagtail Localize
    pip install wagtail wagtail-localize

    # Start a new project
    wagtail start tutorial
    cd .\tutorial
    ```

**Create a database**

Next, migrate the database for the first time:

``` shell
python manage.py migrate
```

That should create a file called ``db.sqlite3`` which contains all of the content.

**Create a user**

Now create a user called ``admin``:

``` shell
python manage.py createsuperuser --email admin@example.com --username admin
```

**Start the development server**

Finally, start a local development server:

``` shell
python manage.py runserver
```

Open up a browser and visit ``http://localhost:8000``. If all those steps completed correctly, you should see the Wagtail welcome screen:

---

![Wagtail welcome screen](/_static/tutorial/wagtail-welcome.png)

---

**Log in to the admin**

You can get to the admin interface by clicking the "Admin interface" link at the botton of the welcome screen. Log in with the user you created earlier.

![Wagtail admin](/_static/tutorial/wagtail-admin.png)
