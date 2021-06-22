.. _commander-vm:

###############
Commander VM
###############

What is the Commander VM?
============================

To use Ansible and configure systems, Dropship needs temporary access to each of the networks its configuring. To do this, Dropship runs in virtual machine that moves between each network by calling the APIs of the virtualization platform it is on. This VM is called the "commander VM." Dropship will operating from this VM, sending out the commands and files needed for deployment, hence the name "commander."

Building a Commander VM
========================

This VM has a few requirements, but can be almost any Linux distro you want. You'll probably want a Linux distro with a GUI to make modifying modules and other Dropship files easier.  

* Distro supports the following:

    *  Python 3
    * ``dnsmasq``
  
* Has multiple interfaces:

    * One interface connected to a network that can connect to the virtualization environment API, probably your production network. 
    * One interface that connects to the different networks during operation.

* Has routing enabled 

Virtualization Platform Requirements
====================================

To prepare cloned systems for their location on the new network, Dropship needs a temporary network where it can reach the cloned systems. This is the bootstrap switch. This is the network the configuration interface on the Commander VM will start on by default, and newly cloned systems are put on so Dropship can give them an IP via DHCP and connect to them to perform the bootstrap stage.