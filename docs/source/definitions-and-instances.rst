.. _definitions-and-instances:

#####################################
Network Definitions and Instances
#####################################

Dropship utilizes two types of files to define a network. First is a "definition" file, which defines hosts, domain, IP ranges, users, and post modules. This serves as a re-usable basis for creating networks. An "instance" file is used to actually fully define a network to be built. The instance file fills in the data and structure in the definition file to create a unique version of the network.

Definition File Overview
========================

A definition file is the re-usable basis for a network, similar to classes or shared libraries in software development. The file takes the format of:

..  code-block::

    COMMAND ARG1 ARG2 ...

Arguments are parsed as similar to shell scripts, so put double quotes around arguments with special characters and spaces.


Definition File Commands
========================

The following is the currently supported commands, and details about their arguments:

NETWORK
*******

``NETWORK`` is a required command, and must be the first command. The only argument is the name of network. It should be unique.

Example:

..  code-block::

    NETWORK testnet


RANGE 
******

``RANGE`` is also a required command. Its only argument is a network range in the format ``IP/PREFIX``. Replace octets (numbers between periods) with a letter that can be overridden with variables in an instance file. This allows network ranges to change between instances. Be sure this same letter is used in the same location for system addresses.

Example (the ``x`` will be able to be replaced in an instance file):

..  code-block::

    RANGE 192.168.x.0/24

DOMAIN 
*******

``DOMAIN`` is another required command. It defines the Windows domain, along with the administrator credentials. The format is:

..  code-block::

    DOMAIN <DOMAIN_NAME> <ADMIN_USERNAME> <ADMIN_USER_PASSWORD>

The ``<DOMAIN_NAME>`` should be the full domain name. Dropship will shorten it when needed.

Example:

..  code-block::

    DOMAIN "HACKNET.fake" "Administrator" "2h@cktheNet!"

HOST 
*****

``HOST`` defines a host. It defines the hostname, the module for the host, and the IP of the host. The format is:

..  code-block::

    HOST <HOSTNAME> <MODULE> <HOST_IP>

The ``<HOSTNAME>`` defines both the hostname assigned to the box, as well as being used to map a host to a post module. ``<MODULE>`` defines the module, using similar notation to importing Python modules, with the module directory as the base (usually ``./modules``). The ``<HOST_IP>`` can either be a static IP, in the range defined in ``RANGE`` with the name letter variable, or ``dhcp``, indicating Dropship to keep the DHCP setting for the host.

Examples:

..  code-block::

    HOST testdc domain.ubuntu_dc_18_04 192.168.x.2
    HOST test-client1 clients.windows10_1909 dhcp

USER 
*****

``USER`` defines a domain user (in Active Directory). The format is:

..  code-block::

    USER <USERNAME> <PASSWORD> <FIRSTNAME> <LASTNAME> 

Example:

..  code-block::

    USER eexample "2Us3theNet!" Edward Example

POSTMOD 
********

``POSTMOD`` defines the use of a post module to configure on a system. The format is:

..  code-block::

    POSTMOD <HOSTNAME> <MODULE> <VARNAME>=<VAR_VAL> ...

``<HOSTNAME>`` is the hostname of the system you want to run this module on. This should match the first value defined on a ``HOST`` line. ``<MODULE>`` defines the module, using similar notation to importing Python modules, with the module directory as the base (usually ``./modules``). Variables can be passed to the module using the format ``<VARNAME>=<VAR_VAL>``. Remember the lines are parsed like shell commands, so avoid spaces or quote your variables. This variables can be defined as many times as needed, or none at all.

Examples:

..  code-block::

    POSTMOD test-client1 post.windows.config.localadmin username=HACKNET\\ttest
    POSTMOD test-client1 post.windows.config.rsat


VAR 
****

``VAR`` defines definition-wide variables, such as the DHCP range. The format is:

..  code-block::

    VAR <VAR_NAME> <VAR_VAL>

If the ``<VAR_VAL>`` is in the form of an IP, Dropship will attempt to fill in same letter as with IPs for the range and hosts.




