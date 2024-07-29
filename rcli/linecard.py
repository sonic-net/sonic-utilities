import click
import os
import paramiko
import sys
import select
import socket
import sys
import termios
import tty

from .utils import get_linecard_ip, get_linecard_hostname_from_module_name, get_linecard_module_name_from_hostname
from paramiko.py3compat import u
from paramiko import Channel

EMPTY_OUTPUTS = ['', '\x1b[?2004l\r']

class Linecard:

    def __init__(self, linecard_name, username, password):
        """
        Initialize Linecard object and store credentials, connection, and channel
        
        :param linecard_name: The name of the linecard you want to connect to
        :param username: The username to use to connect to the linecard
        :param password: The linecard password. If password not provided, it 
            will prompt the user for it
        :param use_ssh_keys: Whether or not to use SSH keys to authenticate.
        """
        self.ip = get_linecard_ip(linecard_name)

        if not self.ip:
            sys.exit(1)

        # if the user passes linecard hostname, then try to get the module name for that linecard
        module_name = get_linecard_module_name_from_hostname(linecard_name)
        if module_name is None:
            # if the module name cannot be found from host, assume the user has passed module name
            self.module_name = linecard_name
            self.hostname = get_linecard_hostname_from_module_name(linecard_name)
        else:
            # the user has passed linecard hostname
            self.hostname = linecard_name
            self.module_name = module_name

        self.username = username
        self.password = password

        self.connection = self._connect()


    def _connect(self):
        connection = paramiko.SSHClient()
        # if ip address not in known_hosts, ignore known_hosts error
        connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connection.connect(self.ip, username=self.username, password=self.password)
        except:
            connection = None
        return connection

    def _get_password(self):
        """
        Prompts the user for a password, and returns the password
        
        :param username: The username that we want to get the password for
        :type username: str
        :return: The password for the username.
        """

        return getpass(
            "Password for username '{}': ".format(self.username),
            # Pass in click stdout stream - this is similar to using click.echo
            stream=click.get_text_stream('stdout')
        )

    def _set_tty_params(self):
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())

    def _is_data_to_read(self, read):
        if self.channel in read:
            return True
        return False
    
    def _is_data_to_write(self, read):
        if sys.stdin in read:
            return True
        return False
    
    def _write_to_terminal(self, data):
        # Write channel output to terminal
        sys.stdout.write(data)
        sys.stdout.flush() 
         
    def _start_interactive_shell(self):
        oldtty = termios.tcgetattr(sys.stdin)
        try:
            self._set_tty_params()
            self.channel.settimeout(0.0)

            while True:
                #Continuously wait for commands and execute them
                read, write, ex = select.select([self.channel, sys.stdin], [], [])
                if self._is_data_to_read(read):
                    try:
                        # Get output from channel
                        x = u(self.channel.recv(1024))
                        if len(x) == 0:
                            # logout message will be displayed
                            break
                        self._write_to_terminal(x)
                    except socket.timeout as e:
                        click.echo("Connection timed out")
                        break
                if self._is_data_to_write(read):
                    # If we are able to send input, get the input from stdin
                    x = sys.stdin.read(1)
                    if len(x) == 0:
                        break
                    # Send the input to the channel
                    self.channel.send(x)
        finally:
            # Now that the channel has been exited, return to the previously-saved old tty
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)
            pass
        

    def start_shell(self) -> None:
            """
            Opens a session, gets a pseudo-terminal, invokes a shell, and then 
            attaches the host shell to the remote shell.
            """
            # Create shell session
            self.channel = self.connection.get_transport().open_session()
            self.channel.get_pty()
            self.channel.invoke_shell()
            # Use Paramiko Interactive script to connect to the shell
            self._start_interactive_shell()
            # After user exits interactive shell, close the connection
            self.connection.close()


    def execute_cmd(self, command) -> str:
        """
        Takes a command as an argument, executes it on the remote shell, and returns the output
        
        :param command: The command to execute on the remote shell
        :return: The output of the command.
        """
        # Execute the command and gather errors and output
        _, stdout, stderr = self.connection.exec_command(command + "\n")
        output = stdout.read().decode('utf-8')
        
        if stderr:
            # Error was present, add message to output
            output += stderr.read().decode('utf-8')
        
        # Close connection and return output
        self.connection.close()
        return output
