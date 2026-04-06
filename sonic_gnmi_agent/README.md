Sonic Smart-Switch GNMI agent
In order to build the docker gnmi agent image, these 2 dependencies need to be built:
make SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 target/docker-sonic-gnmi.gz
make SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 target/debs/bookworm/libdashapi_1.0.0_amd64.deb

Then you can use this command to build the sonic gnmi agent docker:
make -C SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 src/sonic-utilities/sonic_gnmi_agent clean all

The generated file will be located here:
./target/docker-sonic-gnmi-agent.gz

Preparation of the switch for running the gnmi agent
Sonic gnmi server container will start automatically when the system is booted up. We need to install server certificate for the server processing requests using gnmi_get/gnmi_set/gnmi_cli commands. 

1. Generate server certificate and key.
   Run below command to generate self-signed certificate and copy the .key and .cer to /etc/sonic/tls directory:
       sudo mkdir /etc/sonic/tls
       sudo openssl req -x509 -newkey rsa:4096 -keyout /etc/sonic/tls/server.key -out /etc/sonic/tls/server.cer -days 365 -nodes

2. Add below config at top level in /etc/sonic/config_db.json file:

    "GNMI": {
        "certs": {
            "server_crt": "/etc/sonic/tls/server.cer",
            "server_key": "/etc/sonic/tls/server.key"
        }
    }

4. Reload config
sudo config load

5. Restart gnmi server on the switch after configuration change
  /usr/local/bin/gnmi.sh stop
  /usr/local/bin/gnmi.sh start


Installing and using the agent
1. Copy the ocker-sonic-gnmi-agent.gz file and instal it on the switch:
   docker load -i docker-sonic-gnmi-agent.gz

2. Launch the docker container:
   docker run -it --name=sonic_gnmi_agent --network host sonic-gnmi-agent:latest

3. Execute the gnmi_client operatioons from inside the docker

General Syntax
python gnmi_client.py [options] <subcommand> [subcommand options]
Options
-t, --target: (Optional) Address of the GNMI server formatted as host:port. Defaults to 127.0.0.1:8080.
-d, --debug: (Optional) Enable debug log output. Defaults to False.
-i, --dpu_index: (Optional) Index of the Data Processing Unit (DPU) ranging from 0 to 7. Defaults to 0.
-n, --num_dpus: (Optional) Number of DPUs, between 1 and 8. Defaults to 1.
-s, --sleep_secs: (Optional) Delay in seconds before each batch operation. Defaults to 0.
-b, --batch_val: (Optional) Size of batch operations. Defaults to 10.

Subcommands
update
    Performs an update operation using a JSON template.
    Syntax:
    gnmi_client.py update -f <template_path>
    -f, --filename: (Required) Path to the JSON template file.

replace
    Performs a replace operation using a JSON template.
    Syntax:
    gnmi_client.py replace -f <template_path>
    -f, --filename: (Required) Path to the JSON template file.

delete
    Performs a delete operation based on a JSON template or an XPath.
    Syntax:
    gnmi_client.py delete [-f <template_path>] | [-x <xpath>]
    -f, --filename: Path to the JSON template file.
    -x, --xpath: XPath of the object to be deleted.

get
    Fetches data from the device using a JSON template or an XPath.
    Syntax:
    gnmi_client.py get [-f <template_path>] | [-x <xpath>]
    -f, --filename: Path to the JSON template file.
    -x, --xpath: XPath of the object to be retrieved.

Examples
Update a Device Configuration Using Template:
    gnmi_client.py  -i 0 -n 8 -t 127.0.0.1:8080 -s 5 update -f /sonic/templates/pl_combined.j2
Replace a Configuration with Debug Mode Enabled:
    gnmi_client.py  -i 0 -n 8 -t 127.0.0.1:8080 -s 5 update -d -f /sonic/templates/pl_combined.j2
Delete a Configuration:
    gnmi_client.py  -i 0 -n 8 -t 127.0.0.1:8080 -s 5 delete -f /sonic/templates/pl_combined.j2
Get Configuration Details with Template:
    gnmi_client.py  -i 0 -n 8 -t 127.0.0.1:8080 -s 5 get -f /sonic/templates/pl_combined.j2
Logging
    The gnmi_client provides logging functionality. Enable debug logs using the -d or --debug option to get detailed output for troubleshooting.

Notes
    Ensure your templates are correctly formatted and valid JSON to avoid errors during rendering.
    The default user credentials for gNMI operations are set to cisco/cisco123 in the gnmi_client and may need to be updated based on your environment.

Troubleshooting
If you encounter errors, consider the following:
    Check the gNMI server connectivity (IP address and port).
    Verify access credentials.
    Ensure JSON templates are valid.
    Use the --debug option to obtain detailed logs for debugging.

