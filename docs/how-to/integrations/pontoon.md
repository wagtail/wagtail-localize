# How to integrate with Pontoon

[Pontoon](https://github.com/mozilla/pontoon) is an open source translation management system built and maintained by
Mozilla. This guide explains how to configure Wagtail Localize to use an instance of pontoon for Translation.

## Git repository set up

Pontoon can only work with PO files in a Git repository, so we will need to create a git repo to use as an intermediary
between the two systems.

### Generate an SSH keypair for Wagtail Localize

In order for Wagtail Localize to access the git repository, it must authenticate itself with your git repository host.

The only authentication method it supports at the moment is using an SSH key.

To generate a new keypair, use the `ssh-keygen` command (built in to Mac/Linux. optional feature on Windows):

```shell
ssh-keygen -f wagtail-localize-key -C wagtail-localize
```

It will prompt for a password, leave that blank.

### Create a git repository

Now you need to create a git repo for the PO files to live in. You can use any host for this you like as long as it:

-   Is accessible over the network from both Pontoon and Wagtail
-   Supports deploy keys that can write to the repository (Both GitHub and Gitlab support this)

Note that you do not need to make your repo public as both Pontoon and Wagtail Localize can authenticate using a deploy
key.

Once you've created your repository, add the public key (`wagtail-localize-key.pub`) that you created as a deploy key.
Make sure it has write permissions.

## Configuring Wagtail Localize

In this section, we will configure Wagtail Localize to push source PO files into the repository and pull translations.

### Install the `wagtail-localize-git` plugin

Install `wagtail-localize-git` using pip, and also add it your `requirements.txt`/`pyproject.toml` file:

```shell
pip install wagtail-localize-git
```

Then, add it to your `INSTALLED_APPS` django setting:

```python
INSTALLED_APPS = [
    # ...
    "wagtail_localize",
    # Insert this
    "wagtail_localize_git",
    # ...
]
```

Note that this app won't do anything unless it's configured, so it's safe to add it into your base settings as well.

### Configure your server

#### Install the SSH private key

On your server, you need to add the private SSH key to the SSH keyring so that the `git` command will automatically
use it. There are instructions on how to do this on Heroku at the end of this guide.

#### Configure the `wagtail-localize-git` plugin

On your Wagtail server, you'll need to set two Django settings:

-   `WAGTAILLOCALIZE_GIT_URL` should be set to the SSH git clone URL of your repository

-   `WAGTAILLOCALIZE_GIT_CLONE_DIR` needs to be set to a directory that Wagtail Localize can clone the git repository into.

    If you're running on an ephermeral file system (such as on Heroku), this can be pointed to a temporary directory.
    Wagtail Localize will re-clone the repository if it's ever deleted. It keeps track of what the previous `HEAD`
    commit was in the database so it will not lose track of anything if a deletion occurs.

For example:

```python
WAGTAILLOCALIZE_GIT_URL = "git@github.com:mozilla-l10n/mozilla-donate-content.git"
WAGTAILLOCALIZE_GIT_CLONE_DIR = "/tmp/wagtail-content-for-pontoon.git"
```

Finally, you need to set up a cron job to run the `sync_git` management command periodically. I suggest that you
set it to run at least hourly, but ideally, every 10 minutes to allow translations to move between Pontoon and Wagtail
quickly.

## Appendix: Installing an SSH private key on a Heroku app

Setting up an SSH private key on a Heroku can be done by putting the private key into an environment variable,
and creating a setup script that copies that key into a place where git/SSH can see it.

### Encoding the key

Firstly, encode the SSH private key with `base64` and add it to the app with an environment variable called `SSH_PRIVATE_KEY`:

```bash
base64 -w0 wagtail-localize-key
```

Copy the string that this outputs, and paste it into the following command (or use the web UI):

```bash
heroku config:set -a application-name-here SSH_PRIVATE_KEY=<paste base64 string here>
```

### For regular (non container) apps

For regular Heroku apps, add a `.profile` file in the root folder of your project and insert the following:

```bash
#!/usr/bin/env bash

# Copy SSH private key to file, if set
# This is used for talking to GitHub over an SSH connection
if [ $SSH_PRIVATE_KEY ]; then
    echo "Generating SSH config"
    SSH_DIR=/app/.ssh

    mkdir -p $SSH_DIR
    chmod 700 $SSH_DIR

    echo $SSH_PRIVATE_KEY | base64 --decode > $SSH_DIR/id_rsa

    chmod 400 $SSH_DIR/id_rsa

    cat << EOF > $SSH_DIR/config
StrictHostKeyChecking no
EOF

    chmod 600 $SSH_DIR/config

    echo "Done!"
fi
```

### For container apps

For container-based apps, you can use a Docker entrypoint to set up the SSH key.

Copy the following file into your repo, or combine it with your existing Docker entrypoint if you already have one:

```bash
#!/usr/bin/env bash

# Copy SSH private key to file, if set
# This is used for talking to GitHub over an SSH connection
if [ $SSH_PRIVATE_KEY ]; then
    echo "Generating SSH config"
    SSH_DIR=/app/.ssh

    mkdir -p $SSH_DIR
    chmod 700 $SSH_DIR

    echo $SSH_PRIVATE_KEY | base64 --decode > $SSH_DIR/id_rsa

    chmod 400 $SSH_DIR/id_rsa

    cat << EOF > $SSH_DIR/config
StrictHostKeyChecking no
EOF

    chmod 600 $SSH_DIR/config

    echo "Done!"
fi

exec "$@"
```

Run `chmod +x docker_entrypoint.sh` to make it executable.

Then add `ENTRYPOINT ["/app/docker-entrypoint.sh"]` to your `Dockerfile` (update the filename if it's different on your project).
