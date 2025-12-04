import click
import functools
import os
import subprocess
import sys

import click._bashcomplete as _bashcomplete


class VtyshCommand(click.Command):
    """
    Custom Click command class that integrates vtysh help functionality.
    This provides enhanced help by showing both Click help and vtysh subcommands.
    """

    # List of vtysh commands that support completion
    vtysh_completion_commands = []

    def __init__(self, name, vtysh_command_prefix, **kwargs):
        """
        Initialize the VtyshCommand.

        Args:
            name: Command name
            vtysh_command_prefix: The vtysh command prefix (e.g., "show ip route")
            **kwargs: Other Click command arguments
        """
        self.vtysh_command_prefix = vtysh_command_prefix
        super().__init__(name, **kwargs)

    def parse_args(self, ctx, args):
        """Track vtysh command args for later use"""
        help_options = ['-h', '--help', '-?', '?']
        self.raw_args = []
        for arg in args:
            if arg in help_options:
                break
            self.raw_args.append(arg)
        # SONiC CLI accepts '?' as a hidden help option, handle it explicitly here
        if '?' in args:
            click.echo(ctx.get_help())
            ctx.exit()
        return super().parse_args(ctx, args)

    def get_help(self, ctx):
        """Override Click's get_help to provide enhanced vtysh help."""
        formatter = click.HelpFormatter()

        # Try the full command first
        is_valid = False
        if len(self.raw_args) == 0:
            is_valid = True
            last_valid_command = self.vtysh_command_prefix
        else:
            arg_prefix = ' '.join(self.raw_args[:-1])
            full_command_prefix = f"{self.vtysh_command_prefix}"
            if arg_prefix != "":
                full_command_prefix += f" {arg_prefix}"
            full_command = f"{self.vtysh_command_prefix} {' '.join(self.raw_args)}"
            # Handle partial commands (ie, "show ip route sum")
            completions = self.get_vtysh_completions(full_command)
            if len(completions) == 1:
                last_valid_command = f"{full_command_prefix} {completions[0]}"
                is_valid = True

        if not is_valid:
            # If the full command failed, work backwards to find last valid command prefix
            last_valid_command = self.vtysh_command_prefix
            for arg in self.raw_args:
                test_command = f"{last_valid_command} {arg}"

                # Handle partial commands (ie, "show ip route sum")
                completions = self.get_vtysh_completions(test_command)
                if len(completions) == 1 or (len(completions) > 1 and completions[0] == arg):
                    test_command = f"{last_valid_command} {completions[0]}"
                elif len(completions) > 1:
                    usage_args = self.get_usage_args(last_valid_command)
                    formatter.write_usage(last_valid_command, usage_args)
                    formatter.write(f'Try "{last_valid_command} -h" for help.')
                    formatter.write_paragraph()
                    formatter.write_paragraph()
                    formatter.write_text(f'Error: Too many matches: {", ".join(sorted(completions))}')
                    return formatter.getvalue().rstrip()

                vtysh_help_text = self.get_vtysh_help(test_command)
                if vtysh_help_text and "% There is no matched command." in vtysh_help_text:
                    usage_args = self.get_usage_args(last_valid_command)
                    formatter.write_usage(last_valid_command, usage_args)
                    formatter.write(f'Try "{last_valid_command} -h" for help.')
                    formatter.write_paragraph()
                    formatter.write_paragraph()
                    formatter.write_text(f'Error: No such command "{arg}".')
                    return formatter.getvalue().rstrip()

                last_valid_command = test_command

        # Add Usage section
        usage_args = self.get_usage_args(last_valid_command)
        formatter.write_usage(last_valid_command, usage_args)

        # Add description
        description = None
        if self.raw_args:
            description = self.get_vtysh_command_description(last_valid_command)
        elif self.callback and self.callback.__doc__:
            description = self.callback.__doc__.strip().split('\n')[0]
        if description:
            formatter.write_paragraph()
            formatter.write_text(description)

        # Add Options section
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)
        if opts:
            with formatter.section("Options"):
                formatter.write_dl(opts)

        # Add Commands section (from vtysh)
        vtysh_subcommands = self.get_vtysh_subcommands(last_valid_command)
        if len(vtysh_subcommands) > 0:
            with formatter.section("Commands"):
                formatter.write_dl(vtysh_subcommands)

        return formatter.getvalue().rstrip()

    def get_usage_args(self, command):
        """Set usage args appropriately for nested vs. leaf commands."""
        vtysh_subcommands = self.get_vtysh_subcommands(command)
        if vtysh_subcommands:
            return "[OPTIONS] COMMAND [ARGS]..."
        return "[OPTIONS]"

    def get_vtysh_command_description(self, command):
        """Get description for the current command from vtysh help."""
        # remove last arg
        curr_command = command.split()[-1]
        prev_command = command.split()[:-1]
        vtysh_subcommands = self.get_vtysh_subcommands(" ".join(prev_command))
        for c, d in vtysh_subcommands:
            if c == curr_command:
                return d
        return ""

    def get_vtysh_completions(self, cmd_prefix):
        """
        Get completion options from vtysh for the given command.
        """
        subcommands = self.get_vtysh_subcommands(cmd_prefix, completion=True)
        completions = []
        for cmpl, _ in subcommands:
            if any(c.isupper() for c in cmpl) or (cmpl.startswith("(") and cmpl.endswith(")")):
                # skip user-defined arguments like VRF_NAME or A.B.C.D, or ranges like (1-100)
                continue
            completions.append(cmpl)
        return completions

    def get_vtysh_subcommands(self, command, completion=False):
        """Get subcommands from vtysh for the given command."""
        vtysh_help_content = self.get_vtysh_help(command, completion)
        if (not vtysh_help_content or "Error response from daemon:" in vtysh_help_content
           or "failed to connect to any daemons" in vtysh_help_content):
            return []

        subcommands = []
        lines = vtysh_help_content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Vtysh help format is typically: "subcommand    description"
            parts = line.split(None, 1)  # Split on whitespace, max 2 parts
            if len(parts) >= 1:
                subcommand = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""

                # Only filter out obvious non-subcommands
                if (subcommand and subcommand != '<cr>' and
                   not subcommand.startswith('%') and
                   not subcommand.startswith('Error:')):
                    subcommands.append((subcommand, description))
        return subcommands

    @functools.lru_cache()
    def get_vtysh_help(self, cmd_prefix, completion=False):
        """
        Get help for a vtysh command.
        """
        try:
            help_command = f"{cmd_prefix}"
            help_command += "?" if completion else " ?"
            result = subprocess.run(
                ['vtysh', '-c', help_command],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Check if command succeeded
            if result.returncode == 0:
                help_content = result.stdout.strip()
            else:
                # If there's an error, it might be in stderr
                help_content = result.stderr.strip() if result.stderr else None
            return help_content

        except Exception:
            return None


def vtysh_command(vtysh_command_prefix):
    """
    Factory function to create a VtyshCommand class with the given command prefix.

    Args:
        vtysh_command_prefix (str): The vtysh command prefix (e.g., "show ip route")

    Returns:
        A partial VtyshCommand class that can be used with @click.command(cls=...)
    """
    VtyshCommand.vtysh_completion_commands.append(vtysh_command_prefix)

    class _VtyshCommand(VtyshCommand):
        def __init__(self, name, **kwargs):
            super().__init__(name, vtysh_command_prefix, **kwargs)

    return _VtyshCommand


_orig_bashcomplete = _bashcomplete.bashcomplete


def custom_bashcomplete(cli, prog_name, complete_var, complete_instr):
    """
    Custom bashcomplete function that integrates vtysh completion.
    """
    mode = os.environ.get(complete_var)
    if mode == "complete":
        command = os.environ.get("COMP_WORDS", "")
        for base_command in VtyshCommand.vtysh_completion_commands:
            if command.startswith(base_command):
                vtysh_cmd = VtyshCommand(command, base_command)
                completions = vtysh_cmd.get_vtysh_completions(command)
                for c in completions:
                    print(c)
                sys.exit(0)
    return _orig_bashcomplete(cli, prog_name, complete_var, complete_instr)


_bashcomplete.bashcomplete = custom_bashcomplete
