# Getting Started

Dropship has a lot of moving parts, so can seem pretty complex. This guide will try its best to step you through how Dropship is designed to work and how this design works to construct your networks.

## Network Definitions

Dropship does configurations per Network. A Network is a series of systems under a single network subnet, most likely with a domain, and other network variables. A Network is defined in a definition file. This definition does not contain specific implementation information like the switch name to allow a definition to be more portable between similar environments (Similar means the environments have access to similar resources, such as the internet. Environments that are not similar for example are an environment with internet access and another environment that does not have internet access.) or allow the network to be repeated in the same environment.

## Host

A Host is a representation of a single system, to which one or modules can be applied. Hosts are referred to by their hostname. A least module of **router**, **domain**, **dhcp**, **service**, or **client** will need to be assigned to a Host to actually construct it, but one or more **post** modules can be assigned to the Host as well. 

## Network Instances

A network instance is a implementation of of a network definition. Instance-unique data is defined in an instance file, which can contain one or more instances. Dropship will track instances you have created with it to provide some protection against rebuilding the same network twice. Dropship does not track when you delete an instance though, so you'll have to update Dropship's data yourself.




groups all  about a single network, with a single domain, under the term "Network." Service and Client type systems are tied to a single Networks. During each configuration step, Dropship goes through each Network sequentially and runs the step for the Network's Service or Client systems.

## Routers

Routers connect Networks together. Due to this, routers are bootstrapped and deployed separately from network systems. As indicated above, they are the first to run in each configuration step.


## Configuration Stages

To keep the parts of deployment distinct and separate from each other, configuration is divided into different stages based on system type and then based on the step in configuration the system is in.

The **system types** are as follows, and appear in the order they are configured:
* **Routers**: Systems that connect different networks together and provide other network services (such as NAT)
* **Services**: Systems that provide services to the network, such Active Directory (a special service, always deployed before any other service), DHCP, DNS etc.
* **Clients**: Systems that represent end-user systems and endpoints. They are deployed last as they usually depend on services to be configured correctly (like AD)

For each system type, their configuration is split into three, what we'll refer to as **configuration steps**. These steps are as follows in the order they run:
* **Bootstrap**: This is where a system receives its base configuration, such as any static IPs, hostnames, and packages are installed. This is mainly due to systems at this point be having access to the internet. The configured network may not have internet access at all, so packages are installed here.
* **Deploy**: This is where the service or main functionality of the system is configured, such as setting up the domain, configuring DHCP, and connecting to the domain.
* **Post**: This is configuration done once the network is configured. This is finishing touches to the networks configuration, such as Group Policy importing, user simulation deployment, and vulnerable configurations.

Each configuration step is completed across all system types before moving to the next configuration step, so the routers are bootstrapped, then the services, then the clients, after which the routers are deployed, then services, etc.


## Modules

Modules consist of a Python class and Ansible files that perform one or more of the configuration stages for a system. A Module provides a single service or role, which is set as the Module's Role in its Python class (the ```__ROLE__``` variable). This role entry marks it for a certain system and configuration stage combination.

Common roles, and their corresponding systems and configuration steps are as follows:
* **router**: The module builds a **Router** system that provides networking functionality to the network. These modules will have **Bootstrap** and **Deploy** stage files, and sometimes **Post** stage files. **router** modules have a unique, two-step bootstrap process.
* **domain**: The module builds a **Service** system that provides the Active Directory Domain Controller. These modules will have **Bootstrap** and **Deploy** stage files, and sometimes **Post** stage files. This modules role also has the job of creating domain users.
* **dhcp**: The module builds a **Service** system that provides DHCP to the network. These modules will have **Bootstrap** and **Deploy** stage files, and sometimes **Post** stage files. This modules role also requires a special Ansible file to get DHCP leases called ```dhcp.yml```.
* **service**: The module builds a more general **Service** system. These modules will have **Bootstrap** and **Deploy** stage files, and sometimes **Post** stage files. 
* **client**: The module builds a **Client** system that most likely will be connected to a domain. These modules will have **Bootstrap** and **Deploy** stage files, and sometimes **Post** stage files.
* **post**: This module provides **Post** stage functionality. These modules will only have **Post** stage files.

Modules are organized into the ```modules``` directory, but can be organized as seen fit, as long as it supports being imported as a Python module. During the setup process, modules will be referred to by their Python module name.



## Images

Images are common operating system templates that can be used by one or more modules. Dropship will clone these images, then perform Ansible configurations on them to build them according to the modules requested for a Host. 

Dropship only has a few global rules to templates, the rest will depend on the modules you plan to use with the image. You'll need to refer to documentation for those modules to build a correct image.

These global rules are:
* An Image should always utilize DHCP to get their initial address. 
* An Image should have unique identifiers removed to ensure cloned systems are different per clone (think sysprep for Windows)