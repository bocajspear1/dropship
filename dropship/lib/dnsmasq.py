import os
import subprocess 
import logging
import getpass
import time

from dropship.lib.helpers import get_command_path

logger = logging.getLogger('dropship')

# Controls and managers DNSmasq for Dropship
# 
# dnsmasq provides the DHCP required to get initial access to the cloned VMs.
# Dropship reads the DHCP lease file, then matches the VMs based on MAC address.
# Once all systems are bootstrapped, the dnsmasq service is stopped so to not interfere with 
# the new network's DHCP, it it is configured.
#
class DropshipDNSMasq():

    def __init__(self, config):
        self._config = config
        self._proc = None
        self._leases_path = "/tmp/ds-dnsmasq.leases"
        self._pid_path = "/tmp/ds-dnsmasq.pid"
    
    def start(self):
        if os.path.exists(self._pid_path):
            self.stop()
            time.sleep(2)

        sudo_path = get_command_path('sudo')
        dnsmasq_path = get_command_path('dnsmasq')\
        
        if dnsmasq_path == "":
            logger.error("dnsmasq path is empty. Is dnsmasq installed?")
            return False

        sudo_command = [
            sudo_path,
            dnsmasq_path,
            "--strict-order",
            "--bind-interfaces",
            "--log-facility=/tmp/ds-dnsmasq.log",
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
            "--dhcp-hostsfile=/tmp/ds-dnsmasq.hosts",
            "--dhcp-range={},{},24h".format(self._config['range_start'], self._config['range_end']),
            "-s", "dropship", 
            "-u", getpass.getuser()
        ]

        self._proc = subprocess.Popen(sudo_command)

        self._proc.poll()

        if self._proc.returncode != None:
            outs, errs = proc.communicate()
            logger.error(outs)
            logger.error(errs)

            raise ValueError("DNSMasq failed to start")
        logger.info("DNSmasq process started")

    def stop(self):
        if os.path.exists(self._pid_path):
            pid = open(self._pid_path, "r").read().strip()
            subprocess.check_output(["/bin/kill", pid])
            logger.info("DNSmasq process stopped")
        else:
            logger.warning("DNSmasq process already stopped")

    def get_ip_by_mac(self, mac_addr):
        mac_addr = mac_addr.lower()

        if not os.path.exists(self._leases_path):
            return None

        leases_file = open(self._leases_path, "r")
        lease_data = leases_file.read()
        leases_file.close()

        for line in lease_data.split("\n"):
            line_data = line.split(" ")
            if len(line_data) > 4:
                lease_mac = line_data[1]
                if lease_mac.lower() == mac_addr:
                    return line_data[2]

        return None



