.. _dropship-basics:

###############
Dropship Basics
###############

How Dropship is Organized
=========================

Dropship is a provisioning and network building framework built using Ansible to enable the creation of rapidly deployed, consistent, and flexible network environments. It operates using modules, consisting of Python code and Ansible scripts, in three distinct stages to build a network from virtual machine templates to a unique network. Modules can span one or more of these stages. The stages are:

* **Bootstrap Stage**: Cloning and preparing VMs for the network, such as setting addresses and hostnames. Packages might also be installed here to prepare a generic template for a particular role in the network. This stage basically takes templates and converts them to unique hosts prepared for a certain role.
* **Deploy Stage**: This is configuring the clones VMs for the roles they have. For routers, this is setting up routing rules. For services, this is configuring the services. For client systems, this might be joining a domain.
* **Post Stage**: This is any final touches to the systems, such as configuring permissions. This stage continues to individualize systems, as this phase allows for more specific configurations per system.

However, to ensure the network is built in an order that allows things to operate correctly, systems will execute in a certain order based on their system type. Modules that deploy certain services have a label that indicates their system type. The order of the system types are:

* **Routers**: Any router are deployed first to ensure at least local routing is available when the other systems are deployed.
* **Services**: All network services are deployed next. Although grouped together, certain special services will be built first.

    * **Domain**: Any domain controllers will be run first of all services. This ensures all services and clients after will have domain access
    * **DHCP**: DHCP servers will be deployed to ensure any clients get the addressing they need. DHCP servers have special modules so that Dropship can gather address information from them to access clients.
    * **Other** Services: Any other services will be deployed after this, such as web servers and email services.
* **Clients**: Finally, clients will be deployed.

How Dropship Works
==================

In Dropship, a network structure is defined in a "network definition." This dictates the systems the network contains, the domain configuration, users and other variables. Network definitions are defined in a network definition file (``.netdef`` files). 

Here is an example of a definition file:

..  code-block::

    NETWORK testnet
    RANGE 192.168.x.0/24
    DOMAIN "HACKNET.fake" "Administrator" "PASSWORD"
    HOST testdc domain.ubuntu_dc_18_04 192.168.x.2
    HOST test-client1 clients.windows10_1909 dhcp
    HOST test-dhcp services.ubuntu_dhcp 192.168.x.3
    VAR dhcp_range_start 192.168.x.10
    VAR dhcp_range_end 192.168.x.100
    USER ttest "2Us3theNet!" Tommy Test 
    POSTMOD test-client1 post.windows.config.localadmin username=HACKNET\\ttest

However, to use a definition, a "network instance" must be created with its own network instance file (``netinst`` files). A network instance contains information for a single instance of the network defined in a definition. This allows a definition to be used multiple times for both the same and slightly modified networks. For example, using instances, two networks with the same hosts, domain, users, but with different IP ranges can be deployed. This is great for competitions or otherwise shared environments. 

Here is an example of a network instance file:

..  code-block::

    NETINSTANCE test
    INSTOF testnet
    ROUTER gateway networking.vyos EXTERNAL=dhcp test=1
    SWITCH vmbr5
    PREFIX test-
    OCTET x 1
    VAR network_dns_forwarder 1.1.1.1

Dropship takes these files, combines the information in them to build Ansible scripts for each stage and each system type. To access the new systems, Dropship operates on a special VM, called the **commander VM** that moves between networks as it deploys them by accessing the virtualization platform's APIs, which requiring no extra management from the user. Dropship will clone, configure, and then apply the Ansible scripts to the new systems. Dropship also tracks what it's done so far so that even if something fails or the process is stopped, it will pick up at the set of systems it was configuring before.

Next Steps
==========

* For more information about the special Commander VM, see :ref:`commander-vm`
* For more on modules, see :ref:`modules`
* For building definition and instance files, see :ref:`definitions-and-instances`