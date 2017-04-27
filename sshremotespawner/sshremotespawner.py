import errno
import os
import pipes
import pwd
import shutil
import signal
import sys
import grp
import warnings
import paramiko
import subprocess
from subprocess import Popen, call
from tempfile import mkdtemp


from tornado import gen
from traitlets import (
    Any, Bool, Dict, Instance, Integer, Float, List, Unicode,
    validate,
)
from jupyterhub.traitlets import Command, ByteSpecification
from jupyterhub.utils import random_port, url_path_join

from jupyterhub.spawner import Spawner

class SSHRemoteSpawner(Spawner):
    """
    A Spawner that uses `subprocess.Popen and paramiko.ssh_client` to start single-user servers as remote processes.

    Requires remote UNIX users matching(!) the authenticated users to exist.
    Does not work on Windows.
    """
    
    server_url = Unicode("localhost", config=True, \
        help="url of the remote server")
    hub_api = Unicode("http://127.0.0.1:8081/hub/api", config=True, \
        help="define the location of the Juypterhub-server")
    user_home = Unicode("/home", config=True, \
        help="define home location of all users on remote-server. '/{user}' will be added automatically")
    user_shell = Unicode("/bin/bash", config=True, \
        help="define shell from remote user")
    INTERRUPT_TIMEOUT=KILL_TIMEOUT=TERM_TIMEOUT=10
    pid = Integer(0)

    def load_state(self, state):
        """Restore state about spawned single-user server after a hub restart.

        Local processes only need the process id.
        """
        super(SSHRemoteSpawner, self).load_state(state)
        if 'pid' in state:
            self.pid = state['pid']

    def get_state(self):
        """Save state that is needed to restore this spawner instance after a hub restore.

        Local processes only need the process id.
        """
        state = super(SSHRemoteSpawner, self).get_state()
        if self.pid:
            state['pid'] = self.pid
        return state

    def clear_state(self):
        """Clear stored state about this spawner (pid)"""
        super(SSHRemoteSpawner, self).clear_state()
        self.pid = 0

    def user_env(self, env):
        """Augment environment of spawned process with user specific env variables."""
        env['USER'] = self.user.name
        home = self.user_home+"/"+self.user.name # default: /home/{self.user.name}
        shell = self.user_shell # default: /bin/bash
        # These will be empty if undefined,
        # in which case don't set the env:
        if home:
            env['HOME'] = home
        if shell:
            env['SHELL'] = shell
        return env

    def get_env(self):
        """Get the complete set of environment variables to be set in the spawned process."""
        env = super().get_env()
        env = self.user_env(env)
        return env

    @gen.coroutine
    def start(self):
        """Start the single-user server."""
        self.port = random_port()
        env = self.get_env()
        api_url = self.hub_api
        arg = {
            "user": self.user.name,
            "port": self.port,
            "log": 'INFO',
            "base_url": 'user/{name}'.format(name=self.user.name),
            "hub_host": '',
            "hub_prefix": '/',
            "hub_api_url": api_url, # http://127.0.0.1/hub/api or with specific Jupyterhub-server address
            "notebook_dir": '~/notebooks',
            "ip": '0.0.0.0'
        }
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.server_url, username=self.user.name)
        # first we define the environment, similar to the LocalProcessSpawner. Then we execute the remote jupyterhub-singleuser-server command
        stdin, stdout, stderr = self.ssh_client.exec_command('export PATH="{PATH}" ; export VIRTUAL_ENV="{VIRTUAL_ENV}" ; export USER="{USER}" ; export JUPYTERHUB_CLIENT_ID="{JUPYTERHUB_CLIENT_ID}" ; export JUPYTERHUB_API_TOKEN="{JUPYTERHUB_API_TOKEN}" ; export JUPYTERHUB_OAUTH_CALLBACK_URL="{JUPYTERHUB_OAUTH_CALLBACK_URL}" ; export SHELL="{SHELL}" ; export HOME="{HOME}" ; export JUPYTERHUB_HOST="{JUPYTERHUB_HOST}" ; export LANG="{LANG}" ; export JPY_API_TOKEN="{JPY_API_TOKEN}" ; mkdir -p {arg_notebook_dir} ; jupyterhub-singleuser --log={arg_log} --user={arg_user} --base-url={arg_base_url} --hub-host={arg_hub_host} --hub-prefix={arg_hub_prefix} --hub-api-url={arg_hub_api_url} --ip={arg_ip} --port={arg_port} --notebook-dir={arg_notebook_dir} &> jupyterhub_singleuser.log & pid=$! ; echo PID=$pid'.format(PATH=env['PATH'], VIRTUAL_ENV=env['VIRTUAL_ENV'], USER=env['USER'], JUPYTERHUB_CLIENT_ID=env['JUPYTERHUB_CLIENT_ID'], JUPYTERHUB_API_TOKEN=env['JUPYTERHUB_API_TOKEN'], JUPYTERHUB_OAUTH_CALLBACK_URL=env['JUPYTERHUB_OAUTH_CALLBACK_URL'], SHELL=env['SHELL'], HOME=env['HOME'], JUPYTERHUB_HOST=env['JUPYTERHUB_HOST'], LANG=env['LANG'], JPY_API_TOKEN=env['JPY_API_TOKEN'], arg_log=arg['log'], arg_user=arg['user'], arg_base_url=arg['base_url'], arg_hub_host=arg['hub_host'], arg_hub_prefix=arg['hub_prefix'], arg_hub_api_url=arg['hub_api_url'], arg_ip=arg['ip'], arg_port=arg['port'], arg_notebook_dir=arg['notebook_dir']))
        self.pid = int(stdout.readline().replace("PID=", ""))
        call(["ssh", "-N", "-f", "%s@%s" % (self.user.name, self.server_url), "-L {port}:localhost:{port}".format(port=self.port)])
        p=Popen(["pgrep", "-f", "L {port}:localhost:{port}".format(port=self.port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        self.tunnelpid = int(out)
        if self.__class__ is not SSHRemoteSpawner:
            # subclasses may not pass through return value of super().start,
            # relying on deprecated 0.6 way of setting ip, port,
            # so keep a redundant copy here for now.
            # A deprecation warning will be shown if the subclass
            # does not return ip, port.
            if self.ip:
                self.user.server.ip = self.ip
            self.user.server.port = self.port
        return (self.ip or '127.0.0.1', self.port)

    @gen.coroutine
    def poll(self):
        """Poll the spawned process to see if it is still running.

        If the process is still running, we return None. If it is not running,
        we return 0.
        """
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command('ps -p {PID} -o pid='.format(PID=self.pid))
            firstline = stdout.readline()
            if int(firstline) == self.pid:
                return None
        except:
            return 0
        return 0


    @gen.coroutine
    def _signal(self, sig):
        stdin, stdout, stderr = self.ssh_client.exec_command('kill {PID}'.format(PID=self.pid))
        Popen(["kill", "{PID}".format(PID=self.tunnelpid)])
        stdin, stdout, stderr = self.ssh_client.exec_command('ps -p {PID} -o pid='.format(PID=self.pid))
        pid = stdout.readline()
        try:
            if int(pid) == self.pid:
                return True
        except:
            return False
        return False

    @gen.coroutine
    def stop(self, now=True): # now=True, just kill it
        if not now:
            status = yield self.poll()
            if status is not None:
                return
            self.log.debug("Interrupting %i", self.pid)
            yield self._signal(signal.SIGINT)
            yield self.wait_for_death(self.INTERRUPT_TIMEOUT)

        # clean shutdown failed, use TERM
        status = yield self.poll()
        if status is not None:
            return
        self.log.debug("Terminating %i", self.pid)
        yield self._signal(signal.SIGTERM)
        yield self.wait_for_death(self.TERM_TIMEOUT)

        # TERM failed, use KILL
        status = yield self.poll()
        if status is not None:
            return
        self.log.debug("Killing %i", self.pid)
        yield self._signal(signal.SIGKILL)
        yield self.wait_for_death(self.KILL_TIMEOUT)

        status = yield self.poll()
        if status is None:
            # it all failed, zombie process
            self.log.warning("Process %i never died", self.pid)

