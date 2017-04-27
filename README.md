# SSHRemoteSpawner

Remote SSH Spawner class for JupyterHub to spawn a remote notebook-server and tunnel the port via SSH

## Prerequisites

Python version 3.3 and above is required.

Clone the repo:

```bash
    git clone https://github.com/kreuzert/SSHRemoteSpawner.git
    cd SSHRemoteSpawner
```

Install dependencies:

```bash
    pip install -r requirements.txt
```

## Installation

Install SSHRemoteSpawner to the python environment:

```bash
    pip install -e .
```

## Configuration

### Jupyterhub-Notebook Configuration
Requires remote UNIX users matching(!) the authenticated cn to exist.
Remote-server has to install jupyterhub (https://github.com/jupyterhub/jupyterhub) and the command '$ jupyterhub-singleuser' has to be defined in one of the following pathes: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

### JupyterHub-Server Configuration
Need passwordless SSH access to remote server, need to setup `jupyterhub_config.py`:

```python
c.JupyterHub.spawner_class = 'sshremotespawner.SSHRemoteSpawner'
c.SSHRemoteSpawner.server_url = "remote"
```

There are two options two run a remote Jupyterhub-singleuser-server

1.
The remote server needs a ssh-tunnel for the 8081 port to the Jupyterhub-server.
```bash
user@remote:~/ $ ssh -N -f root@jupyterhubserver -L 8081:localhost:8081
```
-> no further configurations required

2.
Open the Jupyterhub-hub-api port 8081 for the remote server and define the address of the Jupyterhub-hub-api (default: http://127.0.0.1/hub/api)
Configuration example:

```python
c.SSHRemoteSpawner.hub_api = 'http://WWW.XXX.YYY.ZZZ:8081/hub/api' # insert your Jupyterhub-server ip here
c.JupyterHub.hub_ip = '0.0.0.0' # if you want to open the ports for specific ips use iptables
```


Tested with Jupyterhub 0.8.0.dev
