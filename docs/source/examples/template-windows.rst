.. _template-windows:

##################
Windows Templates 
##################


Windows 10
====================

These should be valid for any Windows 10 build.

Installation
*************

In my templates, I configured the user to be ``adminuser``, to help differentiate it from other default users, as well as named the system ``template``. This name should be changed via a Dropship module.

WinRM 
***********

For Ansible to be able to access Windows systems, we need to enable WinRM for remote management. Thankfully, Ansible provides a nice script to help us. In a Administrator level Powershell window, run the following:

..  code-block::

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = "https://raw.githubusercontent.com/ansible/ansible/devel/examples/scripts/ConfigureRemotingForAnsible.ps1"
    $file = "$env:temp\ConfigureRemotingForAnsible.ps1"

    (New-Object -TypeName System.Net.WebClient).DownloadFile($url, $file)

    powershell.exe -ExecutionPolicy ByPass -File $file

Applications
*************

To install applications, I use `Ninite <https://ninite.com/>`_, which is a great way to install a number of applications quickly and easily.

Preparing for Sysprep
**********************

Sysprep will prepare the system for cloning, but we want to ensure we skip Windows setup. This can be done with a ``unattend`` XML file. I use one I crafted `here <https://gist.githubusercontent.com/bocajspear1/36519e2b6612131e2478ce90e550894a/raw/6f1b3031881bf7d98653ddbf5eaf78c0d8a4ba8f/unattend.xml>`_.

I recommend placing it in ``C:\``.

Sysprep
********
..  note:: 

    Before I run Sysprep, I usually create a snapshot of the VM, so I can revert if I forgot something. This is to save time for regenerating things (especially on Windows, which not only takes a very long time, but also has a sysprep limit)

Run Sysprep with the following options in an Administrator console:

..  code-block::

    sysprep.exe /oobe /generalize /unattend:C:\unattend.xml /shutdown

