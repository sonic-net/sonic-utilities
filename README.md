Sonic Smart-Switch GNMI agent
In order to build the docker gnmi agent image, these 2 dependencies need to be built:
make SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 target/docker-sonic-gnmi.gz
make SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 target/debs/bookworm/libdashapi_1.0.0_amd64.deb

Then you can use this command to build the sonic gnmi agent docker:
cd src/sonic-utilities/sonic_gnmi_agent
make SONIC_BUILD_JOBS=4 NOBULLSEYE=1 NOBUSTER=1 clean all

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
1. Copy the docker-sonic-gnmi-agent.gz file and instal it on the switch:
   docker load -i docker-sonic-gnmi-agent.gz

2. Launch the docker container:
   docker run -it --name=sonic_gnmi_agent --network host sonic-gnmi-agent:latest

3. Push configurations to the DPU from inside the docker
   gnmi_client.py -i <dpu_id> -n 8 -t 127.0.0.1:8080 <op> -f <template_name>
      op=update|delete|replace
      Arguments:
	-d, --debug,	 default=False, turn on debug log
    	-i, --dpu_index, default=0, DPU index [0-7]
    	-n, --num_dpus,  default=1, required=False, help="Number of DPUs")
    	-s, --sleep_secs,default=0, Delay before each gnmi batch operation in seconds
    	-b, --batch_val, default=10, Batch operation size
   	-u, --username,  default="admin", GNMI server user name
    	-p, --password,  default="password", GNMI server password
 The example templates files are located in the  /sonic/templates directory

