import click
import utilities_common.cli as clicommon
from natsort import natsorted
from tabulate import tabulate
import utilities_common.multi_asic as multi_asic_util
from utilities_common.constants import PORT_CHANNEL_OBJ

"""
    Script to show LAG and LAG member status in a summary view
    Example of the output:
    acsadmin@sonic:~$ teamshow
    Flags: A - active, I - inactive, Up - up, Dw - down, N/A - Not Available,
           S - selected, D - deselected, * - not synced
     No.  Team Dev       Protocol    Ports
    -----  -------------  ----------  ---------------------------
        0  PortChannel0   LACP(A)(Up)     Ethernet0(D) Ethernet4(S)
        8  PortChannel8   LACP(A)(Up)     Ethernet8(S) Ethernet12(S)
       16  PortChannel16  LACP(A)(Up)     Ethernet20(S) Ethernet16(S)
       24  PortChannel24  LACP(A)(Dw)     Ethernet28(S) Ethernet24(S)
       32  PortChannel32  LACP(A)(Up)     Ethernet32(S) Ethernet36(S)
       40  PortChannel40  LACP(A)(Dw)     Ethernet44(S) Ethernet40(S)
       48  PortChannel48  LACP(A)(Up)     Ethernet52(S) Ethernet48(S)
       56  PortChannel56  LACP(A)(Dw)     Ethernet60(S) Ethernet56(S)

"""

PORT_CHANNEL_APPL_TABLE_PREFIX = "LAG_TABLE:"
PORT_CHANNEL_CFG_TABLE_PREFIX = "PORTCHANNEL|"
PORT_CHANNEL_STATE_TABLE_PREFIX = "LAG_TABLE|"
PORT_CHANNEL_STATUS_FIELD = "oper_status"

PORT_CHANNEL_MEMBER_APPL_TABLE_PREFIX = "LAG_MEMBER_TABLE:"
PORT_CHANNEL_MEMBER_STATE_TABLE_PREFIX = "LAG_MEMBER_TABLE|"
PORT_CHANNEL_MEMBER_STATUS_FIELD = "status"

class Teamshow(object):
    def __init__(self, namespace_option, display_option):
        self.teams = []
        self.teamsraw = {}
        self.summary = {}
        self.err = None
        self.db = None
        self.multi_asic = multi_asic_util.MultiAsic(display_option, namespace_option)

    @multi_asic_util.run_on_multi_asic
    def get_teams_info(self):
        self.get_portchannel_names()
        self.get_teamdctl()
        self.get_teamshow_result()

    def get_portchannel_names(self):
        """
            Get the portchannel names from database.
        """
        self.teams = []
        team_keys = self.db.keys(self.db.CONFIG_DB, PORT_CHANNEL_CFG_TABLE_PREFIX+"*")
        if team_keys is None:
            return
        for key in team_keys:
            team_name = key[len(PORT_CHANNEL_CFG_TABLE_PREFIX):]
            if self.multi_asic.skip_display(PORT_CHANNEL_OBJ, team_name) is True:
                continue
            self.teams.append(team_name)

    def get_portchannel_status(self, port_channel_name):
        """
            Get port channel status from database.
        """
        full_table_id = PORT_CHANNEL_APPL_TABLE_PREFIX + port_channel_name
        return self.db.get(self.db.APPL_DB, full_table_id, PORT_CHANNEL_STATUS_FIELD)

    def get_portchannel_member_status(self, port_channel_name, port_name):
        full_table_id = PORT_CHANNEL_MEMBER_APPL_TABLE_PREFIX + port_channel_name + ":" + port_name
        return self.db.get(self.db.APPL_DB, full_table_id, PORT_CHANNEL_MEMBER_STATUS_FIELD)

    def get_team_id(self, team):
        """
            Skip the 'PortChannel' prefix and extract the team id.
        """
        return team[11:]

    def get_teamdctl(self):
        """
            Get teams raw data from teamdctl.
            Command: 'teamdctl <teamdevname> state dump'.
        """

        team_keys = self.db.keys(self.db.STATE_DB, PORT_CHANNEL_STATE_TABLE_PREFIX+"*")
        if team_keys is None:
            return
        _teams = [key[len(PORT_CHANNEL_STATE_TABLE_PREFIX):] for key in team_keys]

        for team in self.teams:
            if team in _teams:
                self.teamsraw[self.get_team_id(team)] = self.db.get_all(self.db.STATE_DB, PORT_CHANNEL_STATE_TABLE_PREFIX+team)

    def get_teamshow_result(self):
        """
             Get teamshow results by parsing the output of teamdctl and combining port channel status.
        """
        for team in self.teams:
            info = {}
            team_id = self.get_team_id(team)
            if team_id not in self.teamsraw:
                info['protocol'] = 'N/A'
                self.summary[team_id] = info
                self.summary[team_id]['ports'] = ''
                continue
            state = self.teamsraw[team_id]
            info['protocol'] = "LACP"
            info['protocol'] += "(A)" if state['runner.active'] == "true" else '(I)'

            portchannel_status = self.get_portchannel_status(team)
            if portchannel_status is None:
                info['protocol'] += '(N/A)'
            elif portchannel_status.lower() == 'up':
                info['protocol'] += '(Up)'
            elif portchannel_status.lower() == 'down':
                info['protocol'] += '(Dw)'
            else:
                info['protocol'] += '(N/A)'

            info['ports'] = ""
            member_keys = self.db.keys(self.db.STATE_DB, PORT_CHANNEL_MEMBER_STATE_TABLE_PREFIX+team+'|*')
            if member_keys is None:
                info['ports'] = 'N/A'
            else:
                ports = [key[len(PORT_CHANNEL_MEMBER_STATE_TABLE_PREFIX+team+'|'):] for key in member_keys]
                for port in ports:
                    status = self.get_portchannel_member_status(team, port)
                    pstate = self.db.get_all(self.db.STATE_DB, PORT_CHANNEL_MEMBER_STATE_TABLE_PREFIX+team+'|'+port)
                    selected = True if pstate['runner.aggregator.selected'] == "true" else False
                    if clicommon.get_interface_naming_mode() == "alias":
                        alias = clicommon.InterfaceAliasConverter().name_to_alias(port)
                        info["ports"] += alias + "("
                    else:
                        info["ports"] += port + "("
                    info["ports"] += "S" if selected else "D"
                    if status is None or (status == "enabled" and not selected) or (status == "disabled" and selected):
                        info["ports"] += "*"
                    info["ports"] += ") "

            self.summary[team_id] = info

    def display_summary(self):
        """
            Display the portchannel (team) summary.
        """
        print("Flags: A - active, I - inactive, Up - up, Dw - Down, N/A - not available,\n"
              "       S - selected, D - deselected, * - not synced")

        header = ['No.', 'Team Dev', 'Protocol', 'Ports']
        output = []
        for team_id in natsorted(self.summary):
            output.append([team_id, 'PortChannel'+team_id, self.summary[team_id]['protocol'], self.summary[team_id]['ports']])
        print(tabulate(output, header))

# 'portchannel' subcommand ("show interfaces portchannel")
@click.command()
@multi_asic_util.multi_asic_click_options
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def portchannel(namespace, display, verbose):
    """Show PortChannel information"""
    team = Teamshow(namespace, display)
    team.get_teams_info()
    team.display_summary()
