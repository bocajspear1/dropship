# Dropship 

Dropship is a Python-based framework to deploy and configure networks without tedious manual configurations of each system. Dropship uses the Ansible framework to address and configure the virtual machine images.

## Terms

* **module**: A Python file that holds metadata and code for type of system. 
* **template**: A module and its counterpart Ansible files are defined as a template.
* **image**: A pre-built virtual machine used by *templates* as a base. These are usually a base install of an operating system configured to address using DHCP. (This is used during configuration to properly address the system for the final network)
* **network**: A single network, with a switch and a single IP range. Configuration is divided into configuring different networks.

## Overview of Process

In Dropship, the configuration of the network is divided into three stages for three categories of systems.

The three system types are configured in the following order:

1. **Routers**: Since these systems are between networks and provided network communications, these must go first.
2. **Services**: These are network services, like Active Directory or DHCP, so these come next, as the clients will depend on them.
3. **Clients**: This are the "user" systems and endpoints. 

The three stages are as follows:

1. **Bootstrap** - Clone templates and set their addresses and hostnames
2. **Deploy** - Perform configurations on the systems to make them operational (connect to AD, start services, etc.)
3. **Post** - Perform after the fact configurations that depend on services (vulnerabilities, data generators, user simulators etc.)

So the process in its entirety does like this:
```
Bootstrap Routers --> Bootstrap Services --> Bootstrap Clients --> Deploy Routers --> Deploy Services --> Deploy Clients --> Post Routers --> Post Services --> Post Clients
```

Issues with DNSMasq and UDP checksums: https://github.com/projectcalico/felix/issues/40
```
iptables -A POSTROUTING -t mangle -p udp --dport bootpc -j CHECKSUM --checksum-fill
```

Much easier to force use of traditional eth0 interfaces, as this makes deployment much easier. Built-in modules will assume this scheme.