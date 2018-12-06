
## docker setup

    $curl -fsSL get.docker.com -o get-docker.sh && sh get-docker.sh

## How to set up Docker to run without using sudo all the time

I discovered this solution on AskUbuntu after encountering the problem. Let’s go through it now.
There are 3 steps:

    Add the Docker group if it doesn’t already exist:

sudo groupadd docker

2. Add the connected user “$USER” to the docker group. Change the user name to match your preferred user if you do not want to use your current user:

sudo gpasswd -a $USER docker

3. From here you have two options: either logout and then log back in, or run newgrp docker for the changes to take effect.

You should now be able to run Docker without sudo. To test, try this:

docker run hello-world
