import os
import subprocess 
import logging
import getpass

logger = logging.getLogger('dropship')

class DropshipDNSMasq():

    def __init__(self, config):
        self._config = config
        self._proc = None
        self._leases_path = "/tmp/ds-dnsmasq.leases"
        self._pid_path = "/tmp/ds-dnsmasq.pid"
    
    def start(self):
        if os.path.exists(self._pid_path):
            return

        dnsmasqPath = subprocess.check_output(["/bin/sh", '-c', 'which dnsmasq']).strip().decode()

        sudo_command = [
            "/usr/bin/sudo",
            dnsmasqPath,
            "--strict-order",
            "--bind-interfaces",
            "--pid-file={}".format(self._pid_path),
            "--except-interface=lo",
            "--no-ping",
            "--interface={}".format(self._config['interface']),
            "--dhcp-rapid-commit",
            "--quiet-dhcp",
            "--quiet-ra",
            "--listen-address={}".format(self._config['gateway']),
            "--dhcp-no-override",
            "--dhcp-authoritative",
            "--dhcp-leasefile={}".format(self._leases_path),
            "--dhcp-hostsfile=/tmp/ds-dnsmasq.hosts"
            "--dhcp-range {},{},1h".format(self._config['range_start'], self._config['range_end']),
            "-s", "dropship", 
            "-u", getpass.getuser()
        ]

        self._proc = subprocess.Popen(sudo_command)
        logger.info("DNSmasq process started")

    def stop(self):
        pid = open(self._pid_path, "r").read().strip()
        subprocess.check_output(["/bin/kill", pid])
        logger.info("DNSmasq process stopped")
