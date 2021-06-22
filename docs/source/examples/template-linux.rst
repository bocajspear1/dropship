.. _template-ubuntu:

##################
Ubuntu Templates 
##################


Ubuntu 20.04 Server
====================

Ubuntu 20.04 is a distro used by a number of Dropship modules by default. These instructions should be valid for any version 18.04+.

Installation
*************

In my templates, I configured the user to be ``adminuser``, to help differentiate it from other default users, as well as named the system ``template``. This name should be changed via a Dropship module. I also did NOT use LVM, which seems to not use the entire disk by default. However, you are free to use whatever configuration fits your environment.


Networking 
***********

First, we need to set Ubuntu to use the ``ethX`` pattern, which is much more predictable. We can do this by editing the ``GRUB_CMDLINE_LINUX`` line in the file ``/etc/default/grub`` to:

..  code-block::

    GRUB_CMDLINE_LINUX="net.ifnames=0 biosdevname=0"

Then we need to update GRUB config, so the commands we need are:


..  code-block::

    sudo vi /etc/default/grub
    sudo grub-mkconfig -o /boot/grub/grub.cfg

`(Source) <https://www.itzgeek.com/how-tos/mini-howtos/change-default-network-name-ens33-to-old-eth0-on-ubuntu-16-04.html>`_

One of the more important items is to configure ``netplan`` to use the MAC address instead of the system ID. This ensures that when we clone, we will get a different IP for different instances. Do this by adding the following line to ``/etc/netplan/00-installer-config.yaml``, on the same level as the `` `` line:

..  code-block::

    dhcp-identifier: mac

While we are editing this file, we should change the interface name to ``eth0`` So the file should now look like this:

..  code-block::

    network:
      ethernets:
          eth0:
            dhcp4: true
            dhcp-identifier: mac
      version: 2


After this, reboot the machine so the interface naming will change.

"Sysprep"
*********

..  note:: 

    Before I run Sysprep, I usually create a snapshot of the VM, so I can revert if I forgot something. This is to save time for regenerating things (especially on Windows, which not only takes a very long time, but also has a sysprep limit)

While this is usually a term used with Windows, modern Ubuntu systems have a number of items that should be cleaned before cloning, such as the machine ID, logs, and SSH keys. These steps are being gathered into scripts at `this repo <https://github.com/bocajspear1/linux-sysprep>`_. We can use the Ubuntu 18.04, and utilize the shortened links:

..  code-block::

    wget https://bit.ly/2OAKLkA -O sysprep.sh 
    chmod +x sysprep.sh 
    ./sysprep.sh

