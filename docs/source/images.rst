.. _images:

#########
Images
#########

What are Images?
================

Images are common operating system templates that can be used by one or more modules. Dropship will clone these images, then perform Ansible configurations on them to build them according to the modules requested for a host. 

Creating Images
===============

Dropship only has a few global rules to templates, the rest will depend on the modules you plan to use with the image. You'll need to refer to documentation for those modules to build a correct image.

These global rules are:

* An Image should always utilize DHCP to get their initial address. Ensure this DHCP will be unique, since multiple instances of the cloned image will be running during a bootstrap. (For example, recent versions of Ubuntu have moved to using the system ID instead of a MAC for identification during DHCP. Switch Ubuntu images back to using the MAC for more consistent results.) 
* An Image should have unique identifiers removed to ensure cloned systems are different per clone (think sysprep for Windows). Ensure things like machine IDs and SSH host keys are removed or regenerated when cloned.

Using Images
============

Images are mapped from virtualization platform specific identifiers (e.g. VMIDs in Proxmox) to string names in the ``config.json`` file. These names must be set in the modules you want to use that particular image. 

For example, lets say you create an Ubuntu 18.04 image you want the ``ubuntu_dc_18_04`` modules to use, its a Proxmox template with the VMID of 100. In ``config.json``, put a line under the ``vm_map`` key similar to:

..  code-block::

    ...
    "linux.my-new-ubuntu-image": 100
    ...

Then, you'll edit the ``__IMAGE__`` line in the ``ubuntu_dc_18_04`` modules ``__init__.py`` file:

..  code-block:: python

    ...
    __DESC__ = "Ubuntu DC"
    __IMAGE__ = "linux.my-new-ubuntu-image"
    __VARS__ = [""]
    ...
